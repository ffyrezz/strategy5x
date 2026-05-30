# Case Study: VRDN — May 5, 2026 Behavioural Failure

## Event
- **Date:** May 5, 2026
- **Catalyst:** VRDN catalyst event (ambiguous/mixed data)
- **Batch:** Post-B11 live trading

## What Happened
VRDN had a legitimate thesis post-catalyst. The pre-commitment plan existed but was not followed at the critical Branch 3 moment. When the data came in as mixed/ambiguous:
- No 15-minute no-trade hold was observed
- Position was held through the ambiguity without the mandatory Branch 3 reassessment
- Stop loss (KS1) was not executed when triggered
- Result: material loss

## Root Cause
Behavioural failure, not analytical failure. The thesis was valid. The system rules existed. The rules were not followed.

## Post-Mortem Classification
Branch 3 violation + KS1 violation. This is a system discipline failure, not a PCETS failure.

## v2.0 Enforcement Added
- Branch 3 hold timer is now a mandatory field in the pre-commitment plan format
- Cannot be left blank
- Bot reminder sent at T+15min after Branch 3 classification

## Lesson
The plan is not optional when the event is ambiguous. Ambiguity is the most common scenario and the most commonly violated branch. If in doubt, 15-min hold is the default action, not holding or exiting.
