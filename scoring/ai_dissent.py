"""
AI Dissent Module — Perplexity Sonar bear-case generation.

Feature-flagged: only runs when AI_DISSENT_ENABLED=true and
PERPLEXITY_API_KEY is set. Errors gracefully fall back to
deterministic-only scoring (never blocks the pipeline).

CRITICAL: The AI must NOT see the bullish thesis — only scores
and ticker. This prevents rubber-stamping.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

import config

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Simple in-memory cost tracker (resets per process)
_request_count: int = 0
_estimated_cost_usd: float = 0.0
COST_PER_REQUEST = 0.005  # conservative estimate per Sonar request


def is_enabled() -> bool:
    """Check if AI dissent is enabled and API key is configured."""
    return config.AI_DISSENT_ENABLED and bool(config.PERPLEXITY_API_KEY)


def _check_budget() -> bool:
    """Check if we're within the monthly cost budget."""
    return _estimated_cost_usd < config.AI_DISSENT_MAX_MONTHLY_COST_USD


def _build_prompt(ticker: str, scores: dict[str, float | None]) -> str:
    """Build the dissent prompt. Only scores + ticker, NO bullish thesis."""
    score_lines = []
    axis_labels = {
        "sc1": "Catalyst Timing",
        "sc2": "Clinical Evidence",
        "sc3": "Regulatory Path",
        "sc4": "Commercial Potential",
        "sc5": "Cash Runway",
        "sc6": "Liquidity",
        "sc7": "Risk/Reward",
        "sc8": "Sector/Macro",
    }
    for key in ["sc1", "sc2", "sc3", "sc4", "sc5", "sc6", "sc7", "sc8"]:
        val = scores.get(key)
        label = axis_labels.get(key, key)
        score_lines.append(f"  {key.upper()} ({label}): {val if val is not None else 'N/A'}")

    composite = scores.get("composite_score")
    score_block = "\n".join(score_lines)

    return (
        f"You are a skeptical biotech analyst. Given the ticker {ticker} "
        f"with these scoring axes (0-10 scale):\n"
        f"{score_block}\n"
        f"Composite: {composite}\n\n"
        f"Argue AGAINST this trade. Find the strongest bear case. "
        f"Be specific about clinical, regulatory, or competitive risks. "
        f"Respond ONLY in valid JSON: "
        f'{{"verdict": "PROCEED"|"CAUTION"|"BLOCK", '
        f'"dissent_text": "string (max 200 chars)", '
        f'"key_risks": ["string", "string"]}}'
    )


async def get_ai_dissent(
    ticker: str,
    scoring_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Call Perplexity Sonar for bear-case AI dissent.

    Returns:
        {
            "verdict": "PROCEED" | "CAUTION" | "BLOCK",
            "dissent_text": str,
            "key_risks": list[str],
            "ai_enabled": True,
            "error": None,
        }

    On any error, returns a safe fallback that won't block scoring.
    """
    global _request_count, _estimated_cost_usd

    fallback = {
        "verdict": "PROCEED",
        "dissent_text": "",
        "key_risks": [],
        "ai_enabled": False,
        "error": None,
    }

    if not is_enabled():
        fallback["error"] = "AI dissent disabled"
        return fallback

    if not _check_budget():
        fallback["error"] = f"Monthly budget exceeded (${_estimated_cost_usd:.2f})"
        logger.warning("AI dissent budget exceeded: $%.2f", _estimated_cost_usd)
        return fallback

    scores = {
        f"sc{i}": scoring_result.get(f"sc{i}")
        for i in range(1, 9)
    }
    scores["composite_score"] = scoring_result.get("composite_score")

    prompt = _build_prompt(ticker, scores)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.AI_DISSENT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
                timeout=30,
            )

        _request_count += 1
        _estimated_cost_usd += COST_PER_REQUEST

        if resp.status_code != 200:
            fallback["error"] = f"API returned {resp.status_code}"
            logger.warning("AI dissent API error: %s %s", resp.status_code, resp.text[:200])
            return fallback

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(content)

        verdict = parsed.get("verdict", "PROCEED")
        if verdict not in ("PROCEED", "CAUTION", "BLOCK"):
            verdict = "PROCEED"

        return {
            "verdict": verdict,
            "dissent_text": str(parsed.get("dissent_text", ""))[:500],
            "key_risks": [str(r) for r in parsed.get("key_risks", [])][:5],
            "ai_enabled": True,
            "error": None,
        }

    except json.JSONDecodeError as exc:
        fallback["error"] = f"JSON parse error: {exc}"
        logger.warning("AI dissent JSON parse failed: %s", exc)
        return fallback
    except Exception as exc:
        fallback["error"] = f"Request failed: {exc}"
        logger.warning("AI dissent request failed: %s", exc)
        return fallback


def merge_with_deterministic(
    det_verdict: str,
    ai_result: dict[str, Any],
) -> tuple[str, str | None]:
    """
    Merge AI dissent with deterministic DA verdict.

    Rule: If AI returns BLOCK and deterministic returned PROCEED,
    escalate to CAUTION. Otherwise keep deterministic verdict.

    Returns (final_da_verdict, dissent_text_or_none).
    """
    if not ai_result.get("ai_enabled") or ai_result.get("error"):
        return det_verdict, None

    ai_verdict = ai_result.get("verdict", "PROCEED")
    dissent = ai_result.get("dissent_text")

    if ai_verdict == "BLOCK" and det_verdict == "PROCEED":
        return "CAUTION", dissent

    return det_verdict, dissent


def get_cost_summary() -> dict[str, Any]:
    """Return cost tracking summary."""
    return {
        "requests": _request_count,
        "estimated_cost_usd": round(_estimated_cost_usd, 4),
        "budget_usd": config.AI_DISSENT_MAX_MONTHLY_COST_USD,
        "budget_remaining_usd": round(config.AI_DISSENT_MAX_MONTHLY_COST_USD - _estimated_cost_usd, 4),
    }
