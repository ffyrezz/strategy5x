"""
Insert enforcement rules (R10–R13) into the Supabase rules table.

Usage:
    python -m scripts.add_enforcement_rules

Uses the Supabase REST API via the project's configured credentials.
"""

from __future__ import annotations

import json
import logging
import sys

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os

# Supabase REST API (data plane)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nwkhsezifgmdckefbljl.supabase.co")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))
if not SERVICE_KEY:
    logger.error("SUPABASE_SERVICE_KEY or SUPABASE_KEY env var must be set")
    sys.exit(1)
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Enforcement rules — column names match DDL exactly
# rule_category must be IN ('hard_ban','concentration','scoring_threshold',
#   'position_sizing','data_quality','playbook_gate','risk_management','other')
# severity must be IN ('block','warn','info')
RULES = [
    {
        "rule_version": 1,
        "rule_code": "R10",
        "rule_category": "concentration",
        "rule_name": "Concentration Cap",
        "rule_text": "Maximum 5 open positions at any time. Bot blocks /candidate if at capacity.",
        "rule_logic": json.dumps({
            "type": "position_count_check",
            "max_positions": 5,
            "enforcement": "block_candidate_creation",
            "override_allowed": True,
        }),
        "severity": "block",
        "playbooks_applicable": ["A", "B", "C", "D", "E"],
        "is_immutable": False,
        "active": True,
        "changed_by": "system_enforcement_v1",
        "change_reason": "Enforcement mechanism: concentration cap to prevent over-diversification",
    },
    {
        "rule_version": 1,
        "rule_code": "R11",
        "rule_category": "risk_management",
        "rule_name": "Profit Defense Trim",
        "rule_text": "Any position up >=40% triggers mandatory trim alert. Must /trade SELL or /override TRIM with reason.",
        "rule_logic": json.dumps({
            "type": "gain_threshold_alert",
            "thresholds": [
                {"pct": 40, "priority": "critical", "action": "trim_required"},
                {"pct": 25, "priority": "high", "action": "trim_suggested"},
            ],
            "enforcement": "alert_with_required_response",
        }),
        "severity": "warn",
        "playbooks_applicable": ["A", "B", "C", "D", "E"],
        "is_immutable": False,
        "active": True,
        "changed_by": "system_enforcement_v1",
        "change_reason": "Enforcement mechanism: profit defense to lock in gains",
    },
    {
        "rule_version": 1,
        "rule_code": "R12",
        "rule_category": "risk_management",
        "rule_name": "F2 Auto-Exit",
        "rule_text": "Any position down >=35% from avg cost triggers F2 breach alert. Mandatory exit within 30 minutes of market open.",
        "rule_logic": json.dumps({
            "type": "loss_threshold_alert",
            "thresholds": [
                {"pct": -35, "priority": "critical", "action": "mandatory_exit"},
                {"pct": -25, "priority": "high", "action": "stop_warning"},
            ],
            "enforcement": "mandatory_exit_required",
            "exit_deadline_minutes": 30,
        }),
        "severity": "block",
        "playbooks_applicable": ["A", "B", "C", "D", "E"],
        "is_immutable": True,
        "active": True,
        "changed_by": "system_enforcement_v1",
        "change_reason": "Enforcement mechanism: F2 mandatory exit to prevent catastrophic losses",
    },
    {
        "rule_version": 1,
        "rule_code": "R13",
        "rule_category": "risk_management",
        "rule_name": "Weekly Triage Response",
        "rule_text": "RED positions in weekly triage must receive /hold or /trade within 24 hours. No response = exit.",
        "rule_logic": json.dumps({
            "type": "triage_response_required",
            "flag": "RED",
            "response_deadline_hours": 24,
            "default_action": "exit",
            "valid_responses": ["/hold", "/trade"],
        }),
        "severity": "warn",
        "playbooks_applicable": ["A", "B", "C", "D", "E"],
        "is_immutable": False,
        "active": True,
        "changed_by": "system_enforcement_v1",
        "change_reason": "Enforcement mechanism: weekly triage accountability for RED positions",
    },
]


def insert_rules() -> None:
    """Insert enforcement rules into Supabase via REST API."""
    url = f"{SUPABASE_URL}/rest/v1/rules"

    for rule in RULES:
        logger.info("Inserting rule %s: %s", rule["rule_code"], rule["rule_name"])
        try:
            resp = httpx.post(url, headers=HEADERS, json=rule, timeout=15)
            if resp.status_code in (200, 201):
                data = resp.json()
                rule_id = data[0]["id"] if isinstance(data, list) and data else "unknown"
                logger.info("  OK: %s (id=%s)", rule["rule_code"], rule_id)
            elif resp.status_code == 409 or "duplicate" in resp.text.lower():
                logger.info("  SKIPPED (already exists): %s", rule["rule_code"])
            else:
                logger.error("  FAILED (%d): %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("  ERROR: %s — %s", rule["rule_code"], exc)


def main() -> None:
    """Entry point."""
    logger.info("Inserting enforcement rules R10–R13 into Supabase...")
    insert_rules()
    logger.info("Done.")


if __name__ == "__main__":
    main()
