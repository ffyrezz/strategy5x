# PCETS VIX Regime State Machine

Full documentation in `pcets/README.md` Section 3.

## VIX Levels

| VIX | Regime | Action |
|-----|--------|--------|
| <18 | Normal | All entries, standard sizing |
| 18–22 | Normal-Cautious | All entries, size haircut flag |
| 22–26 | Elevated | All entries, note regime |
| 26–30 | High-Risk | CAUTION → BLOCK for A/B. T-7 to T-14 only. ≤50% size |
| >30 | Crisis | A/B BLOCKED. Exception: pre-committed + catalyst ≤5 days |

## Three-State Internal Model

| Regime | XBI Signal | Special Rules |
|--------|-----------|---------------|
| Bull | XBI > 50d MA rising | All archetypes, standard sizing |
| Neutral | XBI ±5% of 50d MA | SC11 required |
| Bear | XBI < 50d MA by >5% | SC≥8 required, size –40%, SC11 mandatory |

## Rule
⚠️ VIX must always be fetched live. Never hardcode.
