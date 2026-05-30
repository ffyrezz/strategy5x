# Strategy 5.x + PCETS — Unified System v2.0

> **Version:** 2.0 — Merged Canonical (May 31, 2026)
> **Status:** ACTIVE — Single source of truth. Supersedes all prior PCETS files and Strategy 5.x scoring documentation.
> **Repository:** ffyrezz/strategy5x · branch: pcets-v2-integration
> **Last Updated:** May 31, 2026
> **Overrides Logged:** STRATEGY5X-SCORECARD · STRATEGY5X-REGIME · STRATEGY5X-PLAYBOOKS

---

## Architecture Overview

Strategy 5.x is the **operating system**. PCETS v2.0 is the **primary entry engine** running on top of it. They are not competing systems — they are two layers of the same machine.

```
Layer 1 — Infrastructure (Strategy 5.x)
  Supabase PostgreSQL · Telegram bot · GitHub Actions · Railway.app
  VIX+XBI dual-regime · Position limits · Sunday triage · Monthly audit

Layer 2 — Entry Qualification (PCETS v2.0 universal scorecard)
  Four-gate architecture · Prosecution-first Gate C
  Tiered SC1–SC11 · Five-branch pre-commitment plan · Conviction bands
  Applies to ALL Playbooks I–V, not just biotech post-catalyst

Layer 3 — Playbook Execution (Five-playbook matrix)
  Playbook I (Alpha)    — Fresh Tier 1 post-catalyst mean reversion
  Playbook II (Beta)    — Sell-the-news approvals (paper-only until conversion)
  Playbook III (Re-entry) — Intact-thesis re-entry
  Playbook IV (Secondary) — Secondary event, smaller sizing
  Playbook V (Momentum)   — Commercial-stage hold, no binary catalyst required
```

**Perplexity AI:** Research and qualitative analysis ONLY. Does not manage state.
**Notion:** LEGACY READ-ONLY. All writes → Telegram bot → Supabase.

---

## Table of Contents

1. [Core Thesis](#1-core-thesis)
2. [Unified Regime State Machine](#2-unified-regime-state-machine)
3. [Four-Gate Decision Architecture](#3-four-gate-decision-architecture)
4. [Gate A — Eligibility](#4-gate-a--eligibility)
5. [Gate B — Scoring (SC1–SC11)](#5-gate-b--scoring-sc1sc11)
6. [Gate C — DA Challenge (Prosecution-First)](#6-gate-c--da-challenge-prosecution-first)
7. [Gate D — Pre-Commitment Plan](#7-gate-d--pre-commitment-plan)
8. [Five-Playbook Matrix](#8-five-playbook-matrix)
9. [Conviction Bands](#9-conviction-bands)
10. [Sizing Rules](#10-sizing-rules)
11. [Analyst Classification Tiers](#11-analyst-classification-tiers)
12. [Kill Switch System](#12-kill-switch-system)
13. [Dead Cat Matrix](#13-dead-cat-matrix)
14. [Execution Rules](#14-execution-rules)
15. [Event Archetypes](#15-event-archetypes)
16. [Live Case Studies](#16-live-case-studies)
17. [Backtest Evidence Base](#17-backtest-evidence-base)
18. [v1.0 → v2.0 Key Upgrades](#18-v10--v20-key-upgrades)
19. [Hard Rules — Constitution](#19-hard-rules--constitution)
20. [Known Failure Modes](#20-known-failure-modes)
21. [Session Open / Close Protocol](#21-session-open--close-protocol)

---

## 1. Core Thesis

Biotech small-caps ($200M–$5B market cap) that receive negative FDA catalyst events — CRLs, Phase 3 failures, post-approval data misses — overreact on the crash day. The sell-off overshoots fundamental value because (a) stop losses, margin calls, and sector-rotation selling compound the initial news reaction, (b) retail and momentum sellers dominate Day 0 volume, and (c) buy-side institutions require 1–3 days to assess the event and begin accumulating.

A disciplined entry at T+3 after floor identification captures the mean-reversion leg, exiting at T+7 to T+60 depending on the playbook.

**The system is a loss-avoidance machine first, return generator second.** The primary value is correctly rejecting setups where structural risk is too high, not picking winners. The bear regime backtest (B4) validated this: NKTR (–51.4%), TGTX pre-rejection (–38.9%), BCAB (–16.5%), ANIK (–19.3%) were all correctly blocked.

**Academic Foundation:**

| Study | Sample | Key Finding | PCETS Implication |
|-------|--------|-------------|-------------------|
| Hugstad 2019 | 78 FDA announcements 2011–2018 | 8.3% 1-day, 15.85% 5-day for volume-shock negative events | Primary edge: negative news + volume shock |
| Singh et al. 2022 (MIT/Andrew Lo) | 13,807 clinical trials 2000–2020 | Early biotech 8–10% higher abnormal returns than big pharma | Target $200M–$5B early biotech only |
| Pepperdine/Sturm et al. 2007 | FDA approval events | Approval reactions concentrated on event day — efficient pricing | Playbook Beta weak edge; paper-only |
| Quantitative Mean-Reversion | Phase 2–3 failures | 65% win rate; 40–50% mean reversion buying T+3, holding 80 days | T+3 entry validated |
| CRL Resolution Analysis | 89 CRLs | 41% subsequently approved. 57% facility-related. Class 1: 2mo, Class 2: 6mo | CMC CRLs Tier 1. Path Clarity justified |
| BMJ CRL Disclosure Study | CRL vs. press releases | Sponsors omit most CRL reasons. Safety/efficacy concerns hidden | Gate 3 needs actual CRL content |

**Critical Caveat:** Hugstad 8.3%/15.85% returns are population averages across all regimes from 2011–2018. Every scoring output must display: *"Academic edge is population-level. Current XBI regime affects expected magnitude of reversion. Adjust conviction accordingly."*

---

## 2. Unified Regime State Machine

> **OVERRIDE: STRATEGY5X-REGIME (May 31, 2026)**
> Unified regime check: VIX + XBI dual-dimension. Apply the more conservative of the two at all times.
> `/pcetsregime` is now the single regime check for all entries across all playbooks.

Fetch **both** live VIX and live XBI at the start of ANY entry-related task. Never hardcode either.

### VIX Dimension (Strategy 5.x)

| VIX Range | VIX Regime | Entry Rules |
|-----------|------------|-------------|
| < 18 | Normal | All entries permitted, standard sizing |
| 18–22 | Normal-Cautious | All entries; flag size haircut |
| 22–26 | Elevated | All entries; note regime in output |
| 26–30 | High-Risk | Playbook I/II: CAUTION → auto-escalates to BLOCK. Entry window T-7 to T-14 only. Size ≤50% |
| > 30 | Crisis | Playbook I/II fresh entries BLOCKED. Exception: pre-committed position + catalyst ≤5 days |

### XBI Dimension (PCETS v2.0)

| XBI Condition | XBI Regime | Alpha SC Floor | Beta (Playbook II) | Max Position | Tranche Abort | Phase 1 Window |
|---------------|------------|----------------|---------------------|--------------|---------------|----------------|
| Above both DMAs | BULL | 7/10 | 8/10, standard | 100% | Crash-low break only | T0–T7 |
| Below 50-DMA, above 200-DMA | NEUTRAL | 8/10 | 8/10, time stop halved to T+4 | 75% | –5% T+4 trigger | T0–T8 |
| Below both DMAs | BEAR | 9/10 | SUSPENDED | 50% | –5% T+4 trigger | T0–T10 |
| Below extreme / both | CRISIS | No fresh entries | No fresh entries | Existing only | Kill switches only | N/A |

### Combining Both Dimensions

Apply the **more conservative** regime at all times:

| Example | VIX Says | XBI Says | Effective Regime |
|---------|----------|----------|-----------------|
| Normal market, sector recovering | Normal | BULL | BULL standard |
| Market fine, sector correcting | Normal | NEUTRAL | NEUTRAL rules |
| VIX elevated, sector still above DMAs | High-Risk | BULL | High-Risk governs (≤50% size) |
| VIX normal, sector in bear | Normal | BEAR | BEAR rules (50% size, SC≥9) |
| Both stressed | Crisis | BEAR | CRISIS — no fresh entries |

---

## 3. Four-Gate Decision Architecture

All gates must pass in sequence. If any gate fails, **STOP**. No downstream analysis.

```
Gate A → Gate B → Gate C → Gate D → ENTRY
```

Any gate failure = full stop. No exceptions. No "I'll check the other gates first."

---

## 4. Gate A — Eligibility

✅ **Unified regime check** — `/pcetsregime` (VIX + XBI, more conservative governs)
✅ **Entry timing** — T-3 to T-21 only. T-2/T-1: no fresh entry. T-0: follow plan only.
✅ **Going concern** — SC5 hard disqualify blocks all playbooks
✅ **Position limit** — Max 5 open positions. Bot enforces; `/candidate` rejected if at 5.
✅ **Pre-commitment plan** — Must exist or be created before entry (all 5 branches)
✅ **Price floor** — Stock price < $2.00 = HARD BLOCK regardless of any other criterion

---

## 5. Gate B — Scoring (SC1–SC11)

> **OVERRIDE: STRATEGY5X-SCORECARD (May 31, 2026)**
> Retire flat 10-point equal-weight score. All entries now use PCETS v2.0 tiered criteria architecture SC1–SC11 with structural veto power. Conviction bands PLATINUM/GOLD/SILVER/BRONZE/BLOCKED replace single-number floors.

### Tiered Architecture

The type of criterion passed or failed predicts outcomes — not the total score. TVTX won with SC=6 because it passed all three Tier 1 structural criteria. DAWN lost with SC=8 because it failed Path Clarity in a bear regime.

**Tier 1 — Structural (3 criteria, veto power):**
- 1 structural miss: effective floor –1 point
- 2 structural misses: BLOCK regardless of total score

**Tier 2 — Catalytic (5 criteria, sizing multipliers):**
Determine position sizing and conviction but do not independently invalidate the thesis.

**Tier 3 — Signal Quality (2 criteria, modifiers only):**
Increase conviction when present; failure does not trigger sizing reductions alone.

### Scorecard Criteria

#### SC1 — Crash Magnitude [Tier 2 Catalytic]
- ≥40% single-day crash: +2 points
- 25–39% crash: +1 point
- <25% crash: 0 points (setup may lack edge — flag)

#### SC2 — Thesis Classification [Tier 1 Structural — VETO]
Gate 3 prosecution-first protocol feeds this criterion. Score 4/5 required to pass.
- Fail (≤3/5): Effective floor –1 point
- Fail twice (≤2/5): BLOCK

#### SC3 — Cash Runway [Tier 1 Structural — VETO]
- ≥12 months: PASS (company survives resubmission timeline)
- 6–12 months: CAUTION — mandatory size haircut
- <6 months: HARD VETO — all playbooks blocked
- Fail (6–12m): Effective floor –1 point

#### SC4 — No Dilution Risk [Tier 2 Catalytic]
- No S-3/ATM filed within 90 days: +1 point
- No shelf registration active: +1 point
- Active dilution mechanism: 0 points + KS2 monitoring active

#### SC5 — Volume Exhaustion [Tier 2 Catalytic]
- Event-day volume ≥5× 20-day ADV: +2 points (capitulation confirmed)
- Event-day volume 2–5× ADV: +1 point
- Event-day volume <2× ADV: 0 points (suspicious — entry not validated)

#### SC6 — RSI Oversold [Tier 3 Signal]
- RSI ≤25 at entry: +1 point
- RSI 25–35: +0.5 points (advisory)
- RSI >35 at entry: 0 points

#### SC7 — Analyst Defense [Tier 1 Structural — VETO]
See Section 11 for full analyst classification tiers.
- Requires weighted Gate 5 score ≥2.0 (Bull) / 2.5 (Neutral) / 3.0 (Bear)
- Compound Silence Kill: Gate 5 FAIL + no company PR within 72h = auto REJECT. No score overrides this.
- Fail: Effective floor –1 point

#### SC8 — Pre-Event Run Contamination [Tier 2 Catalytic]
Pre-event run % = (T0 price – T-14 price) / T-14 price × 100
- >25% pre-run: **HARD BLOCK** — speculative premium deflating, not true overreaction
- 15–25% pre-run: CAUTION — SC penalty –1, size haircut 30%
- <15% pre-run: PASS — clean setup signal

#### SC9 — Secondary Event Risk [Tier 2 Catalytic]
- Active secondary binary event within 30 days of entry: –2 points
- PDUFA or Ph3 readout within 14 days: BLOCK
- No secondary event: +1 point
- Note: IOVA B6 (–29.8%) is the canonical SC9 contamination failure

#### SC10 — Short Interest Setup [Tier 3 Signal]
- Short interest ≥15% of float: +1 point (squeeze potential)
- Days-to-cover ≥3: +0.5 points
- Short interest <5%: 0 points

#### SC11 — Path Clarity [Tier 1 Structural — Neutral/Bear ONLY]
Required in Neutral and Bear regimes. In Bull: optional advisory.

| Tier | Description | Bear-Regime Effect |
|------|-------------|-------------------|
| A | Unambiguous short path. Manufacturing-only CRL with one defined admin step. | SC floor –1 point (8/10 instead of 9/10) |
| B | Probable medium path. Clinical but existing data supports resubmission without new trial. | Standard bear floor 9/10 |
| C | Uncertain long path. New data required, trial redesign possible, timeline ≥18 months. | Bear floor raised: 10/10 required or BLOCK |

Special exception: 3/3 structural criteria + Path Clarity Tier A + Bear regime → BRONZE sizing permitted at SC=6. The TVTX case validates this.

- Score 0 (no identifiable path): automatic REJECT in Bear/Neutral regardless of total score
- Fail (Path Clarity Tier C in Bear): effective floor 10/10 or BLOCK

### Scoring Output Format (mandatory from bot on every run)

```
XBI REGIME CHECK
XBI current: XXX.XX | vs 50-DMA: X.X% [ABOVE/BELOW] | vs 200-DMA: X.X% [ABOVE/BELOW]
VIX: XX.X [REGIME]
Effective Regime: [BULL/NEUTRAL/BEAR/CRISIS]

TOTAL SCORE: X/10
Structural: X/3 | Catalytic: X/5 | Signal: X/2
CONVICTION BAND: [PLATINUM/GOLD/SILVER/BRONZE/BLOCKED]
EFFECTIVE FLOOR: X/10 (base X + structural adj X + regime adj X)
MAX POSITION: X% of max ([Bull X% / Neutral X% / Bear X%])
VERDICT: [PROCEED / CAUTION / BLOCK]

Academic edge is population-level. Current XBI regime affects expected magnitude of reversion. Adjust conviction accordingly.
```

---

## 6. Gate C — DA Challenge (Prosecution-First)

> The original 5-question Gate 3 format was structurally biased toward BUY confirmation — every question framed positively, inviting the trader to search for evidence supporting entry rather than disconfirming it. The RCKT T+0 entry before gates were completed is the live case study of this failure.

### Step 1 — Prosecution Brief (MANDATORY before any bull case)

Write 3–5 sentences arguing the strongest possible bear case. Answer all of these:
1. Why is the catalyst weaker than it appears on the surface?
2. What structural risk is the crash-day chart concealing?
3. What is the most likely path to further capital loss from this entry?
4. What prior PCETS backtest event is most analogous to a losing outcome here?
5. If this trade loses, what will the post-mortem identify as the root cause?

### Step 2 — Rate Prosecution Strength (1–5)
- 1: Easily dismissed, bear case clearly wrong
- 2: Weak, some merit but overcomes easily
- 3: Moderate, requires genuine counter-argument
- 4: Compelling, difficult to immediately refute → **automatic Grey Zone**
- 5: Genuinely difficult to overcome → Grey Zone + DA BLOCK-level override required

### Step 3 — Five-Question Test

| Question | Structural Criterion |
|----------|---------------------|
| 1. Is the science still alive? | SC2 Thesis Classification |
| 2. Can the company afford to fix this? | SC3 Cash Runway |
| 3. Is the FDA pathway still viable? | SC3 extension |
| 4. Do remaining programs represent ≥20% of pre-crash market cap independently? | SC9 Pipeline (proportionality test) |
| 5. Are informed investors explicitly defending — new notes, not reiterations? | SC7 Analyst Defense |

Score 4/5 required to pass Gate C.

### Gate C Verdicts

| Gate 3 Score | Prosecution Strength | Verdict |
|-------------|---------------------|---------|
| 5/5 | 1–2 (weak bear) | Full conviction BUY |
| 5/5 | 3–4 (moderate bear) | BUY at 75% of normal size |
| 4/5 | Any | Grey Zone — 50% size, 8/10 scorecard floor |
| ≤3/5 | Any | Grey Zone — 25% size |
| Any | 5 (compelling bear) | Grey Zone + DA BLOCK-level override required |

**DA BLOCK = veto.** Override requires: typed justification (20+ words) + size haircut (≤50%) + all-5-branch plan confirmed.

---

## 7. Gate D — Pre-Commitment Plan

Mandatory before any BUY. Must contain all 5 branches **before** capital is deployed.

| Branch | Scenario | Required Response |
|--------|----------|-------------------|
| 1 — Approval/Positive | Data confirms thesis | 30-min hold before action. No adds after +25% gap. |
| 2 — Failure/CRL | Data invalidates thesis | Exit all within 30 min of open. No averaging down. |
| 3 — Mixed/Ambiguous | Data partially supports thesis | **15-min no-trade hold mandatory.** Then reassess. |
| 4 — No-news/Delay | Event delayed, no data yet | Hold. Reset alert. Do not exit prematurely. |
| 5 — Post-gap/Do-nothing | No clear signal at open | Default: hold. Only stop or invalidation condition overrides inaction. |

**Invalidation Conditions (mandatory in every plan):**
- (a) What must remain true for thesis to hold
- (b) What kills the thesis entirely
- (c) What blocks fresh entry today

Branch 3 fifteen-minute hold is codified from the VRDN May 2026 behavioural failure. It is not a guideline — it is a hard rule.

---

## 8. Five-Playbook Matrix

> **OVERRIDE: STRATEGY5X-PLAYBOOKS (May 31, 2026)**
> Five-playbook matrix operative. AXSM-type commercial momentum holds use Playbook V with trailing stop — no binary catalyst required.

| Playbook | Former Name | Entry Type | SC Floor | Key Rules |
|----------|-------------|-----------|----------|-----------|
| **I (Alpha)** | Playbook A | Fresh Tier 1 post-catalyst overreaction | 7/10 (Bull) / 8/10 (Neutral) / 9/10 (Bear) | No VIX >30. No T-2/T-1. Full 5-branch plan. T+3 preferred entry. |
| **II (Beta)** | Playbook B | Sell-the-news approvals | Paper-only until conversion trigger | 10 paper events + win rate ≥55% + paper EV ≥3% before any live capital. Beta-III = HARD REJECT always. |
| **III (Re-entry)** | Playbook C | Re-entry on intact thesis (VRDN post-approval archetype) | 6/10 minimum | Prior exit rationale documented. No averaging down on failed catalyst. SC11 fresh check required. |
| **IV (Secondary)** | Playbook E | Secondary event, smaller sizing | 5.5/10 minimum | SC9 clean mandatory. 14-day binary risk check. Max 50% of normal size. |
| **V (Momentum)** | *New* | Commercial-stage hold, no binary catalyst | SC1–SC5 check minimum | AXSM archetype. Trailing stop not kill-switch exit. Sunday triage AMBER/RED applies. Monthly review of thesis validity. |

**Beta Sub-Types (Playbook II classification):**

| Sub-Type | Criteria | Action |
|----------|----------|--------|
| Beta-I | Efficient Pricing. Pre-approval run ≥100%, large cap, multiple approved competitors, analyst targets at full-approval price | Paper track only. Does NOT count toward paper conversion trigger. |
| Beta-II | Residual Underpricing. Pre-approval run ≤50%, orphan/rare disease, no prior approved therapy, analyst targets still show upside | Paper track at elevated 9/10 SC floor. Only Beta cohort eligible for conversion to live. |
| Beta-III | Controversy Approval. AdCom voted against OR approval came with restrictions OR partial approval | HARD REJECT. No paper track, no live capital, ever. SRPT Elevidys June 2023 is the canonical Beta-III archetype (SC=7, T+7 return –8.4%). |

**Playbook II Conversion Trigger:** N=10 paper-tracked events + paper win rate ≥55% + paper EV ≥3%. Three-strike kill condition post-conversion (3 consecutive losses → suspend live Beta entries, revert to paper-only).

---

## 9. Conviction Bands

| Band | Criteria | Mean Expected T+7 | Max Position | Trim Trigger | Stop |
|------|----------|-------------------|--------------|--------------|------|
| **Platinum** | Structural 3/3, Catalytic 5/5 | +8% to +15% | 100% of regime max | +25% | –12% |
| **Gold** | Structural 3/3, Catalytic 4/5 | +4% to +8% | 85% of regime max | +15% | –12% |
| **Silver** | Structural 3/3, Catalytic 3/5 | +1% to +4% | 65% of regime max | +10% | –10% |
| **Bronze** | Structural 2/3 or special exception | –1% to +3% | 25% of regime max | +8% | –8% |
| **Blocked** | 2+ structural misses or floor not met | — | No entry | — | — |

SC=9 cohort from B11 adversarial batch: mean T+7 +12.12%, win rate 78%. SC=8: mean T+7 +0.32%, win rate 40% — friction-adjusted negative. Only SC=9 consistently produces positive friction-adjusted returns.

Profit-defense alert: Bot auto-alerts at >+40% gain. Requires `/trim` or `/override TRIM [reason]`.

---

## 10. Sizing Rules

Base position: 20% of DEPLOY bucket per trade.

| Condition | Sizing Modifier |
|-----------|----------------|
| Platinum conviction band | 100% base (20% of deploy) |
| Gold conviction band | 85% base (~17% of deploy) |
| Silver conviction band | 65% base (~13% of deploy) |
| Bronze conviction band | 25% base (~5% of deploy) |
| VIX 26–30 (High-Risk) | ≤50% of calculated size (hard cap) |
| DA BLOCK override | ≤50% hard cap |
| XBI NEUTRAL regime | ×0.75 multiplier |
| XBI BEAR regime | ×0.50 multiplier |
| Cash runway 6–12m (SC3 CAUTION) | –30% of calculated size |
| Beta-II stock (SC7) | –20% of calculated size |
| Price $2–$5 (Elevated Friction) | ≤50% hard cap |
| Tranche structure | T+3: 40% of position / T+5: 35% / T+7: 25% |

**ATR Baseline:** Use pre-event ATR14 (T-14 to T-1). Never crash-day ATR. If post-event ATR14 / pre-event ATR14 > 3.0, use 1.5× pre-event ATR as sizing ATR ceiling.

**Max 14-day binary risk:** 10% of total portfolio.
**Concentration Rule:** No single position >25% of DEPLOY bucket.
**Max open positions:** 5 (bot-enforced).

---

## 11. Analyst Classification Tiers

| Tier | Definition | Contribution (SC7) |
|------|-----------|-------------------|
| **Tier A — Genuine Defense** | New note within 48h, explicit reference to event-day data, price target maintained/revised with written justification, recovery/resubmission pathway view | 1.0 per analyst (1.5 for healthcare specialist) |
| **Tier B — Active Engagement** | New note referencing event within 48h, without full PT justification | 0.5 per analyst (0.75 for specialist) |
| **Tier C — Stale Reiteration** | Rating maintained but no new note referencing event-day data | **0.0 — counts for nothing** |

**Healthcare specialist firms (1.5× weight):** Leerink, Jefferies, Canaccord, RBC, BMO, Needham, Mizuho Healthcare, Piper Sandler, Guggenheim.
**Generalist with active coverage (1.0×):** Goldman, Morgan Stanley, JPMorgan, BofA.
**Boutique without named healthcare focus (0.5×):** All others.

**Gate 5 Pass Thresholds by Regime:**
- Bull (above both DMAs): weighted score ≥2.0
- Neutral/Correcting: weighted score ≥2.5
- Bear (below both DMAs): weighted score ≥3.0

**Compound Silence Kill Condition:** Gate 5 FAIL (score ≤0.9) AND no company PR within 72 hours = automatic REJECT. No scorecard score overrides this.

WVE March 2026 (INLIGHT miss): 4 maintained Buy ratings from Leerink, JonesTrading, Mizuho, Canaccord — all Tier C pre-data reiterations. Under old Gate 5: PASS. Under v2.0: score 0.0, FAIL.

---

## 12. Kill Switch System

| Kill Switch | Trigger | Required Action |
|------------|---------|-----------------|
| KS1 — Floor Break | Price closes below crash-day intraday low | Exit 100% at market open |
| KS2 — Dilution | Prospectus supplement / S-3 / ATM filed post-entry | Exit 100% at market |
| KS3 — Thesis Escalation | New FDA clinical hold, additional patient death, major safety escalation | Exit 100% at market |
| KS4 — Hard Dollar Stop | Position at –15% from average cost | Exit 100% at market |
| KS5 — Time Stop | T+60 for Playbook I, T+7 for Playbook II | Exit 100% at time stop |

**KS3 vs. Unrelated Fear Distinction:** A price drop from unrelated sector fear (RGNX B9: gene therapy selloff, not thesis breach) is NOT KS3. Thesis must be directly implicated. If unclear after 4h review: trim 50%, do not full exit.

**Phase 1 Protection Window:** During Phase 1 (T0 to T+7/8/10 by regime), dead cat matrix signals are **suspended**. Only the five kill switches are active. Bot must not compute or display dead cat scores during Phase 1.

---

## 13. Dead Cat Matrix

Phase 2 only (activates after Phase 1 window per regime). Exit threshold: weighted score ≥4.0.

| Signal | Weight | Interpretation |
|--------|--------|---------------|
| Insider selling — new Form 4 sales post-entry | 2.0 | Highest informational content |
| Crash-low close — close below crash low (not intraday) | 2.0 | KS1 handles intraday; close adds compounding weight |
| VWAP rejected for 5 consecutive sessions post-T+7 | 1.5 | Structural seller resistance |
| RSI makes lower low than T+3 reading, post-T+7 | 1.0 | Deterioration from entry-week baseline |
| Volume declining on recovery attempts post-T+7 | 1.0 | Institutional non-participation |
| Company silent post-T+10, no PR of any kind | 0.5 | Only meaningful compounding other signals |

If compound silence was flagged pre-entry: company silence weight doubles to 1.0 post-T+10.

**Regime-Adjusted Phase 1 Windows:**

| XBI Regime | Phase 1 Window | Phase 2 Activation |
|------------|---------------|-------------------|
| Bull | T0–T+7 | T+7 |
| Neutral | T0–T+8 | T+8 |
| Bear | T0–T+10 | T+10 |

---

## 14. Execution Rules

### Entry
- T-3 to T-21 only. No fresh entry T-2, T-1, T-0.
- Pre-commitment plan must exist before order is placed in Moomoo.
- Entry after gap >25% at open: BLOCKED (no chasing).
- 1-hour cooling-off for unplanned impulse: `/hold TICKER [reason]` → wait 1h minimum.
- T+0 entry prohibition is a **hard rule**, not a guideline.

### Tranche Structure (Playbook I Alpha)
- Tranche 1 (Probe): 40% of position at T+3, confirmed floor
- Tranche 2 (Build): 35% of position at T+5, momentum confirmed
- Tranche 3 (Full): 25% of position at T+7, position fully established

**Tranche Abort Trigger (Neutral/Bear):** If stock closes T+4 more than –5% below T+3 entry price, withhold Tranche 2 until price stability confirmed. Tranche 1 probe stays unless kill switch triggers.

### Exit
- Default: T+7 from entry (or T+7 from catalyst, whichever is later)
- Partial exit allowed at +15% on SC≥8 setups
- Kill switch exits override all other rules
- No averaging down on failed catalyst
- Post-gap >25%: no adds

### Concurrent Position Priority Waterfall
When two qualifying events occur within the same 5-day window and only one slot is available:
1. Score — higher SC wins
2. Playbook type — Playbook I over II (Alpha mean T+7 8.4% vs Beta mean 1.8% in backtest)
3. Tier classification — Tier 1 over Tier 2
4. Regime alignment — Bull/Neutral over Transition over Bear
5. Cash runway — longer runway gets the slot

---

## 15. Event Archetypes

### Tier 1A — Manufacturing-Only CRL
FDA issues CRL citing manufacturing/facility deficiencies only. Drug efficacy and safety not challenged.
- Examples: TVTX B4 (+7.8%), ALDX reproxalap B1-3 (+14.7%)
- PCETS verdict: Strong BUY. Path Clarity Tier A. Entry T+1 to T+3. Bear regime exception permitted at SC=6 with 3/3 structural.

### Tier 1B — Sell-the-News Approval
Drug approved but stock sells off due to overhang clearing or profit-taking.
- Examples: TGTX ublituximab B4 (+37.7%), APLS pegcetacoplan B4 (+15.3%)
- PCETS verdict: High-conviction BUY. SC floor ≥8 required.

### Tier 1C — Phase 3 Primary Endpoint Met
Phase 3 meets primary endpoint with statistical significance. Stock overreacts downward due to sell-the-news or data quality concerns.
- Examples: MDGL resmetirom B5 (+26.3%), KRYS beremagene B5/B9/B10 (+22.7%)
- PCETS verdict: Strong BUY if SC≥8 clean (no pre-event run contamination).

### Tier 2A — Phase 2 Data Hit
Phase 2 positive with sufficient N and clean endpoints.
- PCETS verdict: BUY if SC≥8. Caution if SC=7 in Bear/Transition.

### Tier 2B — AdCom Decision
FDA advisory committee vote. Positive vote ≠ approval.
- Key risk: Beta-III after adcom is extremely dangerous. SRPT Elevidys B5 (–8.4%).
- PCETS verdict: Only enter on 10+ vote margin or manufacturing-only objection. Beta-III = HARD BLOCK.

### Tier 2C — Secondary Event (Playbook IV)
Post-approval secondary catalysts, partnership updates, IND clearances.
- Key risk: SC9 contamination. IOVA B6 (–29.8%) is the canonical failure.
- PCETS verdict: Only via Playbook IV. SC9 clean mandatory.

---

## 16. Live Case Studies

### RCKT — Kresladi PDUFA (B11, June 2022)
- SC=6, Playbook IV. Result: +18.0% T+7.
- **What went right:** SC=6 with clean Tier 1A event and SC9 clean — the structural exception is real.
- **What went wrong:** Entry made at T+0 before gates were completed. RCKT entry at $3.842 was a T+0 knife-catch before Gate 3 was run.
- **Lesson:** Do not reflexively block SC=6. But T+0 entry prohibition is absolute. The +18.0% result obscured a process violation.

### WVE — Wave Life Sciences INLIGHT Miss (March 2026)
- Pre-event run contamination on multiple entries; both underperformed.
- 4 maintained Buy ratings (Leerink, JonesTrading, Mizuho, Canaccord) — all Tier C stale reiterations. Under old Gate 5: PASS. Under v2.0: score 0.0, FAIL.
- **Lesson:** SC8 pre-event run contamination detector is the most important structural filter for RNA platform setups. Gate 5 analyst quality weighting is load-bearing, not cosmetic.

### VRDN — Behavioural Failure (May 5, 2026)
- Valid thesis. Entry outside pre-commitment plan timing. No Branch 3 hold documented. Held through stop without executing KS1. Six trades in one session.
- **Result:** Material loss.
- **Lesson:** Branch 3 mandates a 15-minute no-trade hold then decision. Holding through ambiguity without the hold is the exact failure mode the system was built to prevent. The rules existed. They were not followed.
- **v2.0 enforcement:** Branch 3 hold timer now mandatory in plan format. Unplanned impulse → `/hold TICKER [reason]` → 1-hour cooling-off minimum.

---

## 17. Backtest Evidence Base

Full data: `pcets/backtests/master_backtest_b1_b11.csv`

### Summary Statistics (B1–B11, 90 BUY Signals)

| Metric | Value |
|--------|-------|
| Total BUY signals | 90 |
| Overall Win Rate (T+7 > 0) | 54.4% |
| Mean T+7 Return | +2.0% |
| Median T+7 Return | +1.5% |
| Big Wins (≥+15%) | 9 trades |
| Material Losses (<–5%) | 20 trades |
| Stop hits (kill switch triggered) | 3 confirmed |

### By Batch

| Batch | Regime | Events | BUY Signals | Win Rate | Mean T+7 |
|-------|--------|--------|-------------|----------|----------|
| B1–B3 | Bull/Neutral 2025 | 30 | 4 | 100% | +7.1% |
| B4 | Bear 2021–2024 | 29 | 6 | 67% | +5.9% |
| B5 | Transition 2022–2024 | 21 | 5 | 40% | +6.4% |
| B6 | Bull 2025 | 20 | 8 | 50% | –2.5% |
| B7 | Mixed 2024–2025 | 22 | 12 | 58% | +2.3% |
| B8 | Mid-2023 Recovery | 25 | 14 | 36% | –0.4% |
| B9 | Gap-fill 2022–2024 | 25 | 17 | 53% | +1.6% |
| B10 | Post-approval Secondary | 22 | 10 | 67% | +4.6% |
| B11 | Adversarial T+7 Challenge | 20 | 15 | 53% | +0.9% |

### By SC Score

| SC | n | Win Rate | Mean T+7 | Best | Worst |
|----|---|----------|----------|------|-------|
| 6 | 13 | 54% | –0.1% | +18.0% (RCKT) | –29.8% (IOVA) |
| 7 | 15 | 47% | +0.7% | +10.1% (CGON) | –10.1% (AGIO) |
| 8 | 36 | 58% | +1.3% | +22.7% (KRYS) | –17.9% (DAWN) |
| 9 | 25 | 52% | +4.8% | +37.7% (TGTX) | –16.6% (RGNX) |
| 10 | 1 | 100% | +6.2% | +6.2% | +6.2% |

Only SC=9 consistently produces positive friction-adjusted returns. SC=8 is near zero after friction (~5–9% round-trip).

### Top 10 Wins

| Rank | Ticker | Batch | SC | T+7 | Catalyst |
|------|--------|-------|----|-----|----------|
| 1 | TGTX | B4 | 9 | +37.7% | Ublituximab Ph3 sell-news |
| 2 | MDGL | B5 | 9 | +26.3% | Resmetirom MAESTRO-NASH |
| 3 | KRYS | B5/B9/B10 | 9 | +22.7% | Beremagene FDA approval (×3 batches, all won) |
| 4 | RCKT | B11 | 6 | +18.0% | Kresladi PDUFA sell-the-news |
| 5 | SMMT | B8 | 9 | +18.0% | Ivonescimab NSCLC Ph3 initiation |
| 6 | ALEC | B8 | 9 | +16.7% | AL002 TREM2 Ph2 Alzheimer |
| 7 | APLS | B4 | 8 | +15.3% | Pegcetacoplan sell-news bear regime |
| 8 | ALDX | B1-3 | 8 | +14.7% | 1st CRL reproxalap |
| 9 | ARWR | B6 | 9 | +13.9% | Plozasiran FCS FDA approval |
| 10 | FOLD | B8 | 6 | +11.1% | Amicus post-approval EU filing |

### Top 10 Losses

| Rank | Ticker | Batch | SC | T+7 | Root Cause | v2.0 Block |
|------|--------|-------|----|-----|------------|------------|
| 1 | IOVA | B6 | 6 | –29.8% | Secondary event contamination mid-hold | SC9 + SC6 exception requires clean SC9 |
| 2 | DAWN | B4 | 8 | –17.9% | Bear + Path Clarity Tier C | SC11 BLOCK |
| 3 | RGNX | B9 | 9 | –16.6% | Unrelated gene therapy sector fear | KS3 (not KS1) — trim 50% |
| 4 | DNLI | B8 | 8 | –10.2% | Pre-event +38% run | SC8 HARD BLOCK |
| 5 | AGIO | B4 | 7 | –10.1% | Future-catalyst-dependent thesis | Gate 3 prosecution brief kills this |
| 6 | INSM | B6 | 9 | –10.0% | Liberation Day macro shock | KS3 + trim protocol |
| 7 | NUVL | B7 | 8 | –9.3% | Institutional follow-through absent T+3 | Tranche abort trigger |
| 8 | SRPT | B8 | 9 | –8.4% | Pre-event +52% run | SC8 HARD BLOCK |
| 9 | IMVT | B5 | 8 | –8.4% | Gap violation (+100% pre-market) | Entry gap rule BLOCK |
| 10 | SRPT | B5 | 7 | –8.4% | Elevidys Beta-III adcom voted against | Beta-III HARD REJECT |

### 5 Key Meta-Findings

1. **SC=9 is the only consistently profitable tier.** Mean T+7 +4.76%. SC=8 is friction-adjusted near-zero.
2. **Mid-2023 Recovery (B8) is the most dangerous batch archetype.** Pre-event run contamination is the primary killer — SC8 detector alone would have saved SRPT and DNLI.
3. **The bear rejection engine is the real value.** Every catastrophic outcome correctly blocked. Loss-avoidance > winner-picking.
4. **KRYS is the most reliable ticker archetype.** Three separate batch entries, all +22.7%. Archetype: first-in-class gene therapy approval, clean analyst defense, institutional sponsorship, no secondary risk.
5. **Liberation Day macro contamination (April 2025) is a structural blind spot.** Trim protocol limits but cannot fully prevent systemic macro shocks. KS3 + trim is the best available defense.

---

## 18. v1.0 → v2.0 Key Upgrades

| # | Change | What Changed | Why |
|---|--------|-------------|-----|
| 1 | Regime state machine | 3-state XBI + VIX dual-dimension | Bear signals need different rules; v1.0 was regime-blind |
| 2 | Gate C prosecution-first | Mandatory 3–5 sentence prosecution before bull case | System approved too many weak setups (RCKT T+0 entry) |
| 3 | SC11 Path Clarity | 11th criterion in Neutral/Bear | Events without paths passed on score alone (DAWN) |
| 4 | Analyst Tier A/B/C | Replaces flat analyst count | Stale reiterations inflated SC7 (WVE) |
| 5 | Price floor hard block | <$2 = BLOCK regardless | Sub-$2 friction exceeds target return |
| 6 | SC8 pre-event run contamination | >15% pre-run = HARD BLOCK | SRPT/DNLI failures both traced to pre-run |
| 7 | Five-playbook matrix | Adds Playbook V Momentum | AXSM-type holds were orphaned in v1.0 |
| 8 | Branch 3 mandatory hold | 15-min hold codified in plan | VRDN May 2026 failure |
| 9 | SC6 exception rule | SC=6 + Tier 1A/1B + clean SC9 = valid | RCKT +18.0% confirmed exception is real |
| 10 | ATR pre-event baseline | T-14 to T-1 replaces crash-day ATR | Crash-day ATR inflated by 36–64%, undersized best setups |
| 11 | Playbook Beta reclassified | Mandatory paper-only until conversion trigger | EV negative before friction at stated win rates |
| 12 | Compound silence kill | Gate 5 FAIL + 72h silence = auto REJECT | Silent setups structurally underperform |

---

## 19. Hard Rules — Constitution

These rules are **IMMUTABLE**. No override, no exception, no context.

```
❌ No leveraged ETFs (Playbook I/II)
❌ No Playbook I/II entry without dated catalyst
❌ No deployment beyond DEPLOY bucket
❌ No 14-day binary risk >10% of portfolio
❌ No ⚠️[UNVERIFIED] in qualifying calculations
❌ No fresh Playbook I/II entry at T-2, T-1, or T-0
❌ No fresh Playbook I/II entry with VIX > 30
❌ No more than 5 open positions simultaneously
❌ No averaging down on a failed catalyst
❌ No chasing a positive gap >25%
❌ No entry without a pre-commitment plan (all 5 branches)
❌ No SC5 (cash runway <6 months) entry under any circumstances
❌ No entry with stock price < $2.00
❌ No Beta-III entry (ever — no paper track, no live capital)
❌ No T+0 entry for fresh positions (not a guideline — hard rule)

✅ DA BLOCK = veto. Override: typed justification (20+ words) + size haircut (≤50%) + all-5-branch plan
✅ All overrides flagged at monthly audit
✅ Sunday triage: AMBER/RED require /hold or /exit — silence is a system violation
✅ VIX AND XBI must be fetched live before any entry-related task
✅ Prosecution brief mandatory before bull case in every Gate C
✅ Branch 3 fifteen-minute hold is mandatory — not optional
✅ Analyst stale reiterations count as zero (Tier C = 0.0)
```

---

## 20. Known Failure Modes

| Failure Mode | Example | Trigger | Defense |
|-------------|---------|---------|---------|
| Pre-event run contamination | SRPT B8 –8.4%, DNLI B8 –10.2% | Stock ran >15% before catalyst | SC8 hard block |
| Gap violation | IMVT B5 –8.4% | Stock gapped >25% at open | Entry gap rule |
| Secondary event contamination | IOVA B6 –29.8% | New binary event during hold | SC9 + KS2 |
| Bear + no Path Clarity | DAWN B4 –17.9% | Bear regime, no identifiable path | SC11 in Bear |
| AdCom Beta-III | SRPT B5 –8.4% | AdCom voted against + high beta | Beta-III HARD BLOCK |
| Macro shock | INSM B6 –10.0% | Liberation Day tariffs | KS3 + trim protocol |
| Unrelated sector fear | RGNX B9 –16.6% | Gene therapy selloff — not thesis | KS3 vs KS1 distinction |
| Analyst compound silence | Multiple B8 losses | No analyst defense in 48h | Compound silence kill rule |
| No Branch 3 hold | VRDN May 2026 | Ambiguous data, no 15-min hold | Branch 3 mandatory timer |
| SC=6 + secondary event contamination | IOVA B6 | SC6 + active secondary | SC6 exception requires clean SC9 |
| Stale analyst ratings inflating Gate B | WVE March 2026 | 4 Tier C reiterations passed old Gate 5 | Analyst Tier C = 0.0 |
| T+0 entry before gate completion | RCKT June 2022 | Gates run retroactively on live position | T+0 hard rule, pre-trade checklist |

---

## 21. Session Open / Close Protocol

### Session Open — NO Cold Start

Identify task type and load the appropriate skill:
- `"radar"` → strategy5x-radar skill (v2.0)
- `"score qualitative TICKER"` → strategy5x-score-qualitative skill (v2.0)
- `"DA TICKER"` → strategy5x-da-challenge skill (v2.0)
- `"plan TICKER"` → strategy5x-plan skill (v2.0)
- `"audit"` → strategy5x-audit skill (v2.0)
- `"exit review TICKER"` → strategy5x-exit-review skill (v2.0)

Run Gate A (regime + timing + going concern + positions) before any qualitative analysis. If Gate A fails, state why and stop.

If portfolio context needed → ask for `/portfolio` output from bot.

### Pre-Trade Checklist (read before every Moomoo order)

```
□ Plan exists with all 5 branches?
□ VIX below 26 (or managing existing position)?
□ XBI regime check done?
□ Entry timing T-3 to T-21?
□ Positions below 5?
□ SC8 pre-event run check clean?
□ SC9 secondary event check clean?
□ Prosecution brief written and rated?
□ This action is in my pre-committed branch?

ALL YES = permitted to trade. Any NO = no trade.
```

### Candidate Workflow

1. `"radar"` → candidates (regime pre-checked)
2. `/candidate TICKER` → pipeline (blocked if positions ≥5)
3. Gate A: VIX + XBI + timing + going concern + plan status
4. `/score TICKER` → SC1, SC5, SC6, SC7, SC8 + auto DA
5. `"score qualitative TICKER"` → SC2, SC3, SC4 + invalidation conditions
6. `"DA TICKER"` → bear case + verdict
7. `"plan TICKER"` → 5-branch plan + invalidation conditions
8. `/plan TICKER` → save (entry blocked without this)
9. Bot sends T-7, T-3, T-1 alerts with plan recalled
10. Trade in Moomoo → `/trade TICKER BUY/SELL`
11. Bot profit-defense alert if >+40%
12. `"exit review TICKER"` → 4-gate retrospective
13. `/reflect TICKER` → save lesson

### Session Close

No Notion writes. No fingerprint. No checksum.
1. Summarise what was produced
2. List exact Telegram commands to log
3. Done.

### Telegram Command Reference (v2.0 Overrides)

```
/override STRATEGY5X-SCORECARD Retire flat 10-point equal-weight score. All entries now use PCETS v2.0 tiered criteria architecture SC1-SC11 with structural veto power. Conviction bands PLATINUM/GOLD/SILVER/BRONZE replace single-number floors. Effective May 31 2026.

/override STRATEGY5X-REGIME Unified regime check: VIX + XBI dual-dimension. Apply more conservative of the two. /pcetsregime is now the single regime check for all entries across all playbooks. Effective May 31 2026.

/override STRATEGY5X-PLAYBOOKS Five-playbook matrix now operative: Playbook I Alpha, II Beta paper-only, III Re-entry, IV Secondary, V Momentum. AXSM-type commercial holds use Playbook V trailing stop, no binary catalyst required. Effective May 31 2026.
```

---

*End of Unified System v2.0 — Strategy 5.x + PCETS*
*Next review: Monthly audit or after every 10 new BUY signals, whichever comes first.*
*All state management: Telegram bot → Supabase. Perplexity: research only.*
