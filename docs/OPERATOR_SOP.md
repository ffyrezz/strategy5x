# Strategy 5.x — Operator Standard Operating Procedure

## Daily Routine (5 min)

1. **Check /brief** — Read the morning brief at 8 AM SGT. Review portfolio P&L, upcoming catalysts, and action items.
2. **Review action items** — Complete any items flagged in the brief:
   - Create missing pre-commitment plans (`/plan TICKER bull="..." bear="..." mixed="..."`)
   - Score candidates that need scoring (`/score TICKER`)
   - Acknowledge pending alerts (`/ack ALERT_ID`)
3. **Upload CSV if traded** — If you executed trades through Moomoo, export the positions CSV and send it to the bot as a document. The bot will auto-sync.
4. **Log trades** — Record any entries or exits: `/trade TICKER BUY 100 4.50`

## Catalyst Day Routine (15 min)

1. **Review /plan** — Re-read your pre-commitment plan for the catalyst ticker: `/plan TICKER`
2. **Check /score** — Verify the latest score is current. Re-score if data changed: `/score TICKER`
3. **Set mental stops** — Based on your plan's bear/bull scenarios, know your exact actions.
4. **Acknowledge alerts** — The bot sends T-1 and T-0 alerts. Acknowledge them: `/ack ALERT_ID`
5. **Execute per plan** — Follow the pre-committed plan. If you deviate, note the reason.
6. **Log the trade** — Immediately after: `/trade TICKER SELL 100 5.50`

## Weekly Routine (10 min, Sunday evening)

1. **Review audit summary** — The weekly audit sends automatically at 10 PM SGT Sunday. Check Telegram.
2. **Complete reflections** — Run `/reflect` to see pending reflections. Complete each one:
   `/reflect TICKER "What I learned from this trade"`
3. **Check /status** — Review system health, growth metrics, and any warnings.
4. **Pipeline review** — Scan `/candidate` entries. Remove stale candidates, add new ones.

## Monthly Routine (30 min, first Sunday)

1. **Review growth metrics** — Run `/checkpoint` for the full decision report.
2. **Calibration trend** — Is the Calibration Score improving? If declining 3+ weeks, investigate.
3. **Decision Quality trend** — Are you following plans? Completing reflections?
4. **False Negative review** — Were any rejected candidates actually winners? Adjust criteria.
5. **Threshold review** — Based on data, consider adjusting scoring thresholds or concentration caps.
6. **Data export** — Run `/export` monthly for backup.

## Troubleshooting

### Bot not responding
1. Check Telegram — is the bot process running?
2. Run `/status` — if no response, the process has crashed.
3. Check GitHub Actions — are scheduled jobs still running?
4. Restart: `python -m bot.main`

### Stale data warnings
1. The canary check alerts if positions are >24h old.
2. Upload a fresh CSV via Telegram, or run position sync.
3. If yfinance is down, SC scores may be stale — re-score when data returns.

### Missed alerts
1. Check `/status` for unacked alert count.
2. Run `/brief` manually to see current state.
3. Check the alerts table via `/export` if needed.

### Scoring returns incomplete
1. Check if yfinance is returning data: some tickers may not have analyst targets.
2. SC2/SC3/SC4 are manual-input axes — they return null unless you provide them.
3. SC8 depends on XBI/VIX — if market data is unavailable, it returns null.

### AI Dissent not working
1. Check `AI_DISSENT_ENABLED=true` in environment.
2. Check `PERPLEXITY_API_KEY` is set.
3. Monthly budget may be exhausted — check logs.
4. AI dissent failing is non-blocking; deterministic scoring continues.
