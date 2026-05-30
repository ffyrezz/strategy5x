# PCETS Master Thesis — Post-Catalyst Event Trading System v2.0

> **Version:** 2.0 (May 2026 Canonical)
> **Status:** ACTIVE — This is the single source of truth. All prior research files are superseded by this document.
> **Repository:** ffyrezz/strategy5x · branch: pcets-v2-integration
> **Last Updated:** May 31, 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Core Philosophy](#2-core-philosophy)
3. [VIX Regime State Machine](#3-vix-regime-state-machine)
4. [Four-Gate Decision Architecture](#4-four-gate-decision-architecture)
5. [Scorecard — SC1 to SC11](#5-scorecard--sc1-to-sc11)
6. [Gate 3 Prosecution-First Protocol](#6-gate-3-prosecution-first-protocol)
7. [Playbook Matrix](#7-playbook-matrix)
8. [Kill Switch System](#8-kill-switch-system)
9. [Pre-Commitment Plan — 5 Branches](#9-pre-commitment-plan--5-branches)
10. [Dead Cat Matrix](#10-dead-cat-matrix)
11. [Event Archetypes](#11-event-archetypes)
12. [Sizing Rules](#12-sizing-rules)
13. [Conviction Bands](#13-conviction-bands)
14. [Execution Rules](#14-execution-rules)
15. [Analyst Classification Tiers](#15-analyst-classification-tiers)
16. [Live Case Studies](#16-live-case-studies)
17. [Backtest Evidence Base](#17-backtest-evidence-base)
18. [v1.0 → v2.0 Key Upgrades](#18-v10--v20-key-upgrades)
19. [Hard Rules — Constitution](#19-hard-rules--constitution)
20. [Known Failure Modes](#20-known-failure-modes)

---

## 1. System Overview

PCETS (Post-Catalyst Event Trading System) is a structured, rules-based framework for trading biotech overreaction events — moments where the market misprices a binary catalyst outcome due to panic, ambiguity, or sentiment overshoot. The system is not a prediction engine. It is a filtering and loss-avoidance machine that identifies setups where asymmetric recovery is structurally probable, then gates entries through a four-layer decision architecture.

**Core Thesis:** Biotech stocks with identifiable catalysts frequently overshoot to the downside (or fail to sustain upward moves) due to retail panic, algorithmic selling, or incomplete information processing. PCETS enters after the overreaction has occurred and the information set is largely known, targeting a T+3 to T+7 recovery window.

**System Architecture:**
- State layer: Supabase PostgreSQL (10 tables)
- Interface: Telegram bot (@hengonghuatah888_bot)
- Automation: GitHub Actions (morning brief, catalyst alerts, price sync)
- Hosting: Railway.app
- Research: Perplexity AI (qualitative analysis only — does not manage state)

---

## 2. Core Philosophy

**The system is a loss-avoidance machine first, return generator second.**

The primary value of PCETS is not picking winners — it is correctly rejecting setups where structural risk is too high. The bear regime backtest (B4) validated this: NKTR (–51.4%), TGTX pre-rejection (–38.9%), BCAB (–16.5%) were all correctly blocked. Every BUY signal in B4 outperformed the rejected events by 10+ percentage points on average.

**Prosecution-First Mindset:** Before any bull case is considered, Gate 3 requires a mandatory 3–5 sentence prosecution brief. The system assumes guilty (avoid) until proven innocent (enter).

**Path Clarity as Gating Criterion:** An event that produces correct data but no actionable path forward (no approval, no partnership, no IND, no next milestone) is not a PCETS event. Path Clarity is the 11th scorecard criterion in Neutral and Bear regimes.

---

## 3. VIX Regime State Machine

Fetch live VIX at the start of ANY entry-related task. Never hardcode.

| VIX Range | Regime | Entry Rules |
|-----------|--------|-------------|
| < 18 | Normal | All entries permitted, standard sizing |
| 18–22 | Normal-Cautious | All entries, flag size haircut |
| 22–26 | Elevated | All entries, note regime in output |
| 26–30 | High-Risk | Playbook A/B: CAUTION → auto-escalates to BLOCK. Entry window T-7 to T-14 only. Size ≤50% |
| > 30 | Crisis | Playbook A/B fresh entries BLOCKED. Exception: pre-committed position + catalyst ≤5 days |

**Three-State Regime Model (Internal PCETS):**

| Regime | XBI Condition | Behavior |
|--------|---------------|----------|
| Bull | XBI > 50-day MA, rising | All archetypes active. Standard sizing. |
| Neutral | XBI ±5% of 50-day MA | All archetypes. Path Clarity (SC11) required. |
| Bear | XBI < 50-day MA by >5% | Beta archetypes only (SC≥8 required). Size reduced 40%. SC11 mandatory. |

Bear regime requires Path Clarity (SC11) as a non-negotiable addition to all other criteria. A REJECT on SC11 in Bear/Neutral is an automatic veto regardless of total score.

---

## 4. Four-Gate Decision Architecture

All gates must pass in sequence. If any gate fails, STOP. No downstream analysis.

### Gate A — Eligibility
- ✅ VIX regime check (see Section 3)
- ✅ Entry timing: T-3 to T-21 only. T-2/T-1: no fresh entry. T-0: follow plan only.
- ✅ Going concern: SC5 hard disqualify blocks all playbooks
- ✅ Max 5 open positions (bot enforces; /candidate rejected if at 5)
- ✅ Pre-commitment plan exists or must be created before entry

### Gate B — Scoring
- Bot deterministic: SC1, SC5, SC6, SC7, SC8
- Perplexity qualitative: SC2, SC3, SC4
- Score floors: Playbook A ≥65 | B ≥60 | C ≥60 | E ≥55

### Gate C — DA Challenge
- /score runs auto DA + Perplexity bear case
- DA BLOCK = veto. Override requires: typed justification (20+ words) + size haircut (≤50%) + all-5-branch plan confirmed
- CAUTION + VIX High-Risk/Crisis → auto-escalates to BLOCK

### Gate D — Pre-Commitment Plan
- Mandatory before any BUY. Must contain all 5 branches (see Section 9)
- Must contain invalidation conditions: (a) what must remain true, (b) what kills the thesis, (c) what blocks entry today

---

## 5. Scorecard — SC1 to SC11

### SC1 — Event Classification (Structural)
- **Tier 1:** Manufacturing CRL, approval, Ph3 primary endpoint, PDUFA decision
- **Tier 2:** Ph2 data, secondary endpoint, partner event
- **Tier 3:** IND clearance, preclinical, non-clinical milestone
- **Veto:** Any SC5 (going concern) hard disqualifies regardless of score

### SC2 — Catalyst Quality (Qualitative)
Questions: Is the data clean? Is the overreaction proportionate? Is the thesis intact?
- Score 1 (weak): Data ambiguous or negative; overreaction disproportionate
- Score 2 (moderate): Data mixed; some pathway remains
- Score 3 (strong): Data clear; market clearly overreacted; thesis intact
- Score 4 (exceptional): Clean primary endpoint hit; unambiguous; institutional setup present

### SC3 — Pipeline Dependency (Qualitative)
Is the stock's recovery thesis dependent on a single asset, or does the pipeline provide structural support?
- Score 0: Single asset with no backup
- Score 1: Single lead asset with early backup
- Score 2: Two validated assets
- Score 3: Diversified pipeline, multiple near-term milestones

### SC4 — Analyst Defense (Qualitative — Tier-Classified)
See Section 15 for analyst classification tiers.
- Tier A analysts (target/initiation/upgrade): +2 points each, max 2
- Tier B analysts (reaffirmation with substance): +1 point each, max 2
- Tier C analysts (stale reiterations): 0 points
- Compound silence (48h post-event with no Tier A/B): auto-flag, push toward REJECT

### SC5 — Going Concern (Structural Veto)
- Cash runway < 6 months: HARD VETO, all playbooks
- Cash runway 6–12 months: CAUTION flag, size haircut mandatory
- Cash runway > 12 months: PASS

### SC6 — Institutional Ownership (Structural)
- ≥15% institutional ownership: +1 point
- Major institution on register: +1 point
- Recent 13F addition (within 1 quarter): +1 point

### SC7 — Beta Regression (Structural)
- Beta-I: Beta ≤1.2 — standard entry
- Beta-II: Beta 1.2–2.0 — size haircut 20%
- Beta-III: Beta >2.0 — CAUTION in bear, BLOCK in crisis

### SC8 — Pre-Event Run Contamination (Structural)
- >15% run in T-14 to T-0: HARD BLOCK
- 10–15% run: CAUTION, reduce size 30%
- <10% run: PASS

### SC9 — Secondary Event Risk (Structural)
- Active secondary binary event within 30 days: –2 points
- PDUFA or Ph3 data within 14 days: BLOCK
- No secondary event: +1 point

### SC10 — Price Floor (Structural — Hard Rule)
- Stock price <$2.00 at entry: HARD BLOCK regardless of SC score
- Stock price $2–$5: CAUTION, size ≤50%
- Stock price >$5: PASS

### SC11 — Path Clarity (Qualitative — Neutral/Bear only)
Required only in Neutral and Bear regimes. In Bull: optional advisory.
- Score 0: No identifiable path forward post-event → automatic REJECT in Bear/Neutral
- Score 1: Path exists but unclear timeline
- Score 2: Clear path with defined next milestone ≤12 months
- Score 3: Multiple paths, near-term catalysts confirmed

---

## 6. Gate 3 Prosecution-First Protocol

Before any bull case analysis, the analyst must write a prosecution brief: 3–5 sentences arguing the strongest possible bear case.

**Prosecution Brief Template:**
1. Why is the catalyst weaker than it appears?
2. What structural risk is being ignored?
3. What is the most likely failure scenario at T+7?
4. What prior setup in the backtest is most analogous to a loss?
5. If this trade loses, what will the post-mortem say?

**Grey Zone Rule:** If prosecution strength ≥4/5, setup is automatically Grey Zone and requires DA BLOCK-level override.

---

## 7. Playbook Matrix

| Playbook | Entry Type | SC Floor | Key Rules |
|----------|-----------|----------|-----------|
| A | Fresh entry on Tier 1 event | ≥65 | No VIX >30. No T-2/T-1. Full 5-branch plan required. |
| B | Fresh entry on Tier 2 event | ≥60 | Same restrictions as A. Beta-III = BLOCK in bear. |
| C | Re-entry on thesis still intact | ≥60 | Prior exit rationale documented. No averaging down on failed catalyst. |
| E | Opportunistic/secondary | ≥55 | Smaller sizing. SC9 check mandatory. |

**Prohibited Entries (all playbooks):**
- Leveraged ETFs
- Any entry without dated catalyst
- Entry beyond DEPLOY bucket
- 14-day binary risk >10% of portfolio
- Entry without pre-commitment plan

---

## 8. Kill Switch System

| Kill Switch | Trigger | Required Action |
|------------|---------|------------------|
| KS1 — Stop Loss | Stock drops >12% from entry | Exit all within 30 min of open. No averaging down. |
| KS2 — Thesis Breach | Invalidation condition confirmed | Exit same day regardless of P&L |
| KS3 — Unrelated Fear | Sector-wide selloff unrelated to thesis | Review within 4h. If thesis intact: hold. If uncertain: trim 50%. |

**KS3 Distinction:** A price drop from unrelated sector fear is KS3, not KS1, if underlying event data is clean. Exit depends on thesis integrity, not price magnitude alone.

---

## 9. Pre-Commitment Plan — 5 Branches

| Branch | Scenario | Required Response |
|--------|----------|-------------------|
| 1 — Approval/Positive | Data confirms thesis | 30-min hold before action. No adds after +25% gap. |
| 2 — Failure/CRL | Data invalidates thesis | Exit all within 30 min of open. No averaging down. |
| 3 — Mixed/Ambiguous | Data partially supports thesis | 15-min no-trade hold mandatory. Then reassess. |
| 4 — No-news/Delay | Event delayed, no data yet | Hold. Reset alert. Do not exit prematurely. |
| 5 — Post-gap/Do-nothing | No clear signal at open | Default: hold. Only stop or invalidation condition overrides inaction. |

**Invalidation Conditions (mandatory in every plan):**
- (a) What must remain true for thesis to hold
- (b) What kills the thesis entirely
- (c) What blocks fresh entry today

---

## 10. Dead Cat Matrix

| Signal | Dead Cat (avoid) | Real Overreaction (consider) |
|--------|-----------------|------------------------------|
| Cash runway | <6 months | >12 months |
| Prior run | >30% in T-30 to T-0 | <10% in T-14 to T-0 |
| Analyst response | Silent or downgrade | Defense within 24h |
| Institutional ownership | Selling on form 4/13F | Adding or holding |
| Path forward | No milestone <12 months | Clear next catalyst |
| Beta | >2.5 | <1.5 |
| SC11 (Path Clarity) | Score 0 | Score 2+ |

**Rule:** If 4+ Dead Cat signals present → disqualified regardless of headline catalyst quality.

---

## 11. Event Archetypes

### Tier 1A — Manufacturing-Only CRL
FDA issues CRL citing manufacturing/facility deficiencies only. Drug efficacy and safety not challenged.
- Examples: FILSPARI/TVTX B4 (+7.8%), ALDX reproxalap B1-3 (+14.7%)
- PCETS verdict: Strong BUY. Entry T+1 to T+3.

### Tier 1B — Sell-the-News Approval
Drug approved but stock sells off due to overhang clearing or profit-taking.
- Examples: TGTX ublituximab B4 (+37.7%), APLS pegcetacoplan B4 (+15.3%)
- PCETS verdict: High-conviction BUY. SC floor ≥8 required.

### Tier 1C — Phase 3 Primary Endpoint
Phase 3 meets primary endpoint with statistical significance.
- Examples: MDGL resmetirom B5 (+26.3%), KRYS beremagene B5/B9/B10 (+22.7%)
- PCETS verdict: Strong BUY if SC8 clean (no pre-event run contamination).

### Tier 2A — Phase 2 Data Hit
Phase 2 positive with sufficient N and clean endpoints.
- PCETS verdict: BUY if SC≥8. Caution if SC=7 in bear/transition.

### Tier 2B — AdCom Decision
FDA advisory committee vote. Positive vote ≠ approval.
- Key risk: Beta-III after adcom extremely dangerous. SRPT Elevidys B5 (–8.4%).
- PCETS verdict: Only enter on 10+ vote margin or mfg-only objection. Beta-III = BLOCK.

### Tier 2C — Secondary Event (Playbook E)
Post-approval secondary catalysts, partnership updates, IND clearances.
- Key risk: SC9 contamination. IOVA B6 (–29.8%) is the canonical failure.
- PCETS verdict: Only via Playbook E. SC9 clean mandatory.

---

## 12. Sizing Rules

Base position: 20% of DEPLOY bucket per trade.

| Condition | Sizing Modifier |
|-----------|----------------|
| SC ≥9, clean setup | 100% base (20% of deploy) |
| SC 7–8, no flags | 75% base (15% of deploy) |
| SC 6, Playbook E | 50% base (10% of deploy) |
| VIX 26–30 | ≤50% of calculated size |
| Beta-II stock | –20% of calculated size |
| Cash runway 6–12m | –30% of calculated size |
| DA BLOCK override | ≤50% hard cap |
| Price $2–$5 | ≤50% hard cap |

**Max 14-day binary risk:** 10% of total portfolio.
**Concentration Rule:** No single position >25% of DEPLOY bucket.

---

## 13. Conviction Bands

| Band | SC Score | Mean Expected T+7 | Trim Trigger | Stop |
|------|----------|-------------------|--------------|------|
| Platinum | 9–10 | +8% to +15% | +25% | –12% |
| Gold | 8 | +4% to +8% | +15% | –12% |
| Silver | 7 | +1% to +4% | +10% | –10% |
| Bronze | 6 | –1% to +3% | +8% | –8% |

Profit-defense alert: Bot auto-alerts at >+40% gain. Requires /trim or /override TRIM.

---

## 14. Execution Rules

### Entry
- T-3 to T-21 only. No fresh entry T-2, T-1, T-0.
- Pre-commitment plan must exist before order is placed.
- Entry after gap >25% at open: BLOCKED.
- 1-hour cooling-off for unplanned impulse: /hold TICKER [reason] → wait 1h.

### Exit
- Default: T+7 from entry (or T+7 from catalyst, whichever is later).
- Partial exit allowed at +15% on SC≥8 setups.
- Kill switch exits override all other rules.
- No averaging down on failed catalyst.
- Post-gap >25%: no adds.

### Stop Loss
- 12% from entry price (hard stop, KS1).

### Sunday Triage
- AMBER: held >14 days, no catalyst within 14 days → /hold or /exit required.
- RED: thesis unclear, stop approaching → /hold or /exit required.
- Silence = system violation.

---

## 15. Analyst Classification Tiers

### Tier A — High Signal (counts toward SC4)
- Initiating coverage with target price
- Upgrading to buy
- Raising target ≥15% post-event
- Adding to conviction list
- Published within 48h of catalyst

### Tier B — Moderate Signal (counts toward SC4)
- Reaffirming BUY with substantive event-specific commentary
- Maintaining target with updated model
- Published within 72h

### Tier C — No Signal (does NOT count)
- Stale reiteration, no price target change
- Boilerplate commentary without event analysis
- Published >96h after catalyst

**Compound Silence Rule:** Zero Tier A/B within 48h post-event = negative signal. Flag as "analyst silent", push toward REJECT.

---

## 16. Live Case Studies

### RCKT — Kresladi PDUFA (B11, June 2022)
- SC=6, Playbook E. Result: +18.0% T+7.
- **Lesson:** SC=6 with clean Tier 1A/1B event and SC9 clean is structurally sound. Do not reflexively block SC=6.

### WVE — Wave Life Sciences
- Pre-event run contamination present on two separate entries, both underperformed.
- **Lesson:** SC8 contamination detector is the most important structural filter for RNA platform setups.

### VRDN — May 5, 2026 Behavioural Failure
- Valid thesis. Position entered outside pre-commitment plan timing. No Branch 3 hold documented. Held through stop without executing KS1.
- **Result:** Material loss.
- **Lesson:** Branch 3 mandates a 15-min no-trade hold then decision. Holding through ambiguity without the hold is the exact failure mode the system was built to prevent.
- **v2.0 enforcement:** Branch 3 hold timer now mandatory in plan format.

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

### By Batch

| Batch | Regime | n | Win Rate | Mean T+7 |
|-------|--------|---|----------|----------|
| B1–B3 | Bull/Neutral 2025 | 4 | 100% | +7.1% |
| B4 | Bear 2021–2024 | 6 | 67% | +5.9% |
| B5 | Transition 2022–2024 | 5 | 40% | +6.4% |
| B6 | Bull 2025 | 8 | 50% | –2.5% |
| B7 | Mixed 2024–2025 | 12 | 58% | +2.3% |
| B8 | Mid-2023 Recovery | 14 | 36% | –0.4% |
| B9 | Gap-fill 2022–2024 | 17 | 53% | +1.6% |
| B10 | Post-approval Secondary | 9 | 67% | +4.6% |
| B11 | Adversarial T+7 Challenge | 15 | 53% | +0.9% |

### By SC Score

| SC | n | Win Rate | Mean T+7 | Best | Worst |
|----|---|----------|----------|------|-------|
| 6 | 13 | 54% | –0.1% | +18.0% | –29.8% |
| 7 | 15 | 47% | +0.7% | +10.1% | –10.1% |
| 8 | 36 | 58% | +1.3% | +22.7% | –17.9% |
| 9 | 25 | 52% | +4.8% | +37.7% | –16.6% |
| 10 | 1 | 100% | +6.2% | +6.2% | +6.2% |

### Top 10 Biggest Wins

| Rank | Ticker | Batch | SC | T+7 | Catalyst |
|------|--------|-------|----|-----|----------|
| 1 | TGTX | B4 | 9 | +37.7% | Ublituximab Ph3 sell-news |
| 2 | MDGL | B5 | 9 | +26.3% | Resmetirom MAESTRO-NASH |
| 3 | KRYS | B5/B9/B10 | 9 | +22.7% | Beremagene FDA approval |
| 4 | RCKT | B11 | 6 | +18.0% | Kresladi PDUFA sell-the-news |
| 5 | SMMT | B8 | 9 | +18.0% | Ivonescimab NSCLC Ph3 initiation |
| 6 | ALEC | B8 | 9 | +16.7% | AL002 TREM2 Ph2 Alzheimer |
| 7 | APLS | B4 | 8 | +15.3% | Pegcetacoplan sell-news bear regime |
| 8 | ALDX | B1-3 | 8 | +14.7% | 1st CRL reproxalap |
| 9 | ARWR | B6 | 9 | +13.9% | Plozasiran FCS FDA approval |
| 10 | FOLD | B8 | 6 | +11.1% | Amicus post-approval EU filing |

### Top 10 Worst Losses

| Rank | Ticker | Batch | SC | T+7 | Root Cause |
|------|--------|-------|----|-----|------------|
| 1 | IOVA | B6 | 6 | –29.8% | Secondary event contamination mid-hold |
| 2 | DAWN | B4 | 8 | –17.9% | Bear regime + Path Clarity Tier C |
| 3 | RGNX | B9 | 9 | –16.6% | Unrelated gene therapy sector fear (KS3) |
| 4 | DNLI | B8 | 8 | –10.2% | Pre-event +38% run (SC8 contamination) |
| 5 | AGIO | B4 | 7 | –10.1% | Future-catalyst-dependent thesis |
| 6 | INSM | B6 | 9 | –10.0% | Liberation Day macro shock |
| 7 | NUVL | B7 | 8 | –9.3% | Institutional follow-through absent at T+3 |
| 8 | SRPT | B8 | 9 | –8.4% | Pre-event +52% run (SC8 contamination) |
| 9 | IMVT | B5 | 8 | –8.4% | Gap violation (+100% pre-market) |
| 10 | SRPT | B5 | 7 | –8.4% | Elevidys Beta-III adcom voted against |

### 5 Key Meta-Findings
1. **SC=9 is the only consistently profitable tier.** Mean T+7 +4.76%.
2. **Mid-2023 Recovery (B8) is the most dangerous batch archetype.** Pre-event run contamination is the primary killer.
3. **The bear rejection engine is the real value.** Loss-avoidance > winner-picking.
4. **KRYS is the most reliable ticker archetype.** Three separate batch entries, all +22.7%.
5. **Liberation Day macro contamination cannot be fully defended.** Trim protocol limits but doesn't eliminate systemic shock.

---

## 18. v1.0 → v2.0 Key Upgrades

| # | Change | What Changed | Why |
|---|--------|-------------|-----|
| 1 | Regime state machine | Added 3-state replacing binary | Bear signals need different rules |
| 2 | Gate 3 prosecution-first | Mandatory 3–5 sentence prosecution before bull case | System approved too many weak setups |
| 3 | SC11 Path Clarity | Added as 11th criterion in Neutral/Bear | Events without paths passed on score alone |
| 4 | Analyst Tier Classification | Tier A/B/C replaces flat count | Stale reiterations inflated SC4 |
| 5 | Price floor hard block | <$2 = BLOCK regardless of score | Sub-$2 stocks structurally unsound |
| 6 | SC8 contamination detector | Pre-event run >15% = HARD BLOCK | SRPT/DNLI failures traced here |
| 7 | KS3 unrelated fear | Separate kill switch for sector fear | RGNX was sector fear, not thesis breach |
| 8 | Branch 3 mandatory hold | 15-min hold codified in plan format | VRDN May 2026 failure |
| 9 | SC6 exception rule | SC=6 with Tier 1A/1B still valid | RCKT +18.0% confirmed exception is real |
| 10 | Compound silence rule | 48h analyst silence = negative signal | Silent setups underperform |

---

## 19. Hard Rules — Constitution

These rules are IMMUTABLE.

```
❌ No leveraged ETFs (Playbook A/B)
❌ No Playbook A/B entry without dated catalyst
❌ No deployment beyond DEPLOY bucket
❌ No 14-day binary risk >10% of portfolio
❌ No ⚠️[UNVERIFIED] in qualifying calculations
❌ No fresh Playbook A/B entry at T-2, T-1, or T-0
❌ No fresh Playbook A/B entry with VIX > 30
❌ No more than 5 open positions simultaneously
❌ No averaging down on a failed catalyst
❌ No chasing a positive gap >25%
❌ No entry without a pre-commitment plan (all 5 branches)
❌ No SC5 (going concern) entry under any circumstances
❌ No entry with stock price < $2.00

✅ DA BLOCK = veto. Override: typed justification + size haircut + plan
✅ All overrides flagged at monthly audit
✅ Sunday triage: AMBER/RED require /hold or /exit — silence not accepted
✅ VIX must be fetched live before any entry-related task
✅ Prosecution brief mandatory before bull case in every Gate 3
```

---

## 20. Known Failure Modes

| Failure Mode | Example | Trigger | Defense |
|-------------|---------|---------|----------|
| Pre-event run contamination | SRPT B8 –8.4%, DNLI B8 –10.2% | Stock ran >15% before catalyst | SC8 hard block |
| Gap violation | IMVT B5 –8.4% | Stock gapped >25% at open | Entry gap rule |
| Secondary event contamination | IOVA B6 –29.8% | New binary event during hold | SC9 + KS2 |
| Bear + no Path Clarity | DAWN B4 –17.9% | Bear regime, no identifiable path | SC11 in bear |
| AdCom Beta-III | SRPT B5 –8.4% | Adcom voted against + high beta | Beta-III BLOCK |
| Macro shock | INSM B6 –10.0% | Liberation Day tariffs | KS3 + trim |
| Unrelated sector fear | RGNX B9 –16.6% | Gene therapy selloff | KS3 vs KS1 |
| Analyst compound silence | Multiple B8 losses | No analyst defense in 48h | Compound silence rule |
| No Branch 3 hold | VRDN May 2026 | Ambiguous data, no 15-min hold | Branch 3 mandatory |
| SC=6 + secondary event | IOVA B6 | SC6 + active secondary | SC6 exception requires clean SC9 |

---

*End of PCETS Master Thesis v2.0*  
*Next review: Monthly audit or after every 10 new BUY signals, whichever comes first.*  
*All state management: Telegram bot → Supabase. Perplexity: research only.*
