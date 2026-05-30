# PCETS Four-Gate Architecture

Full documentation in `pcets/README.md` Section 4.

## Gate Summary

| Gate | Name | Who Runs | Fail Condition |
|------|------|----------|----------------|
| A | Eligibility | Bot + manual check | VIX crisis, timing T-2/T-1/T-0, SC5, 5-position limit, no plan |
| B | Scoring | Bot (SC1/5/6/7/8) + Perplexity (SC2/3/4) | Below playbook floor |
| C | DA Challenge | Bot auto-DA + Perplexity bear case | DA BLOCK (veto) |
| D | Pre-Commitment Plan | Perplexity research + manual write | Missing any of 5 branches or invalidation conditions |

## Critical Rule
All gates sequential. If Gate A fails → STOP. Do not proceed to B, C, or D.
