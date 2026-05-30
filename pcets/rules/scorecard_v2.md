# PCETS Scorecard v2.0 — SC1 to SC11

Full criteria documented in `pcets/README.md` Section 5.

## Score Floors by Playbook

| Playbook | Floor |
|----------|-------|
| A | ≥65 |
| B | ≥60 |
| C | ≥60 |
| E | ≥55 |

## SC Assignment Matrix

| Criterion | Who Scores | Method |
|-----------|-----------|--------|
| SC1 Event Classification | Bot | Deterministic |
| SC2 Catalyst Quality | Perplexity | Qualitative |
| SC3 Pipeline Dependency | Perplexity | Qualitative |
| SC4 Analyst Defense | Perplexity | Tier A/B/C classification |
| SC5 Going Concern | Bot | Deterministic (hard veto) |
| SC6 Institutional Ownership | Bot | Deterministic |
| SC7 Beta Regression | Bot | Deterministic |
| SC8 Pre-Event Run | Bot | Deterministic |
| SC9 Secondary Event Risk | Bot | Deterministic |
| SC10 Price Floor | Bot | Deterministic (hard block) |
| SC11 Path Clarity | Perplexity | Qualitative (Bear/Neutral only) |

## Veto Conditions (score irrelevant)
- SC5 (going concern): HARD VETO all playbooks
- SC8 >15% pre-event run: HARD BLOCK
- SC10 price <$2: HARD BLOCK
- SC11 = 0 in Bear/Neutral: AUTO REJECT
- Beta-III in Crisis: BLOCK
