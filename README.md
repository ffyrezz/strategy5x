# Strategy 5.x Growth System

Biotech binary catalyst trading decision-support system. Telegram bot backed by Supabase PostgreSQL.

## Quick Start

### 1. Install dependencies
```bash
cd strategy5x
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your credentials:
# - SUPABASE_URL / SUPABASE_KEY from your Supabase project
# - TELEGRAM_BOT_TOKEN from @BotFather
# - TELEGRAM_CHAT_ID from @userinfobot
```

### 3. Set up Supabase tables
Create the 6 core tables in your Supabase SQL editor. See `prototype-packet-schema.md` for full DDL.

### 4. Run the bot
```bash
python -m bot.main
```

## Architecture

```
User (Telegram) → Bot Handlers → Supabase PostgreSQL
                                    ↑
                  Scheduled Jobs ────┘
                  (APScheduler)
                      ↑
                  Market Data (yfinance)
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | System status and available commands |
| `/status` | Health check: DB, sync freshness, pending alerts |
| `/portfolio` | Detailed position list with P&L |
| `/brief` | Morning brief: portfolio + catalysts + action items |
| `/candidate TICKER` | View or create pipeline candidate |
| `/score TICKER` | Run deterministic scoring + DA checks |
| `/plan TICKER` | View or create pre-commitment plan |
| `/concentration` | Portfolio concentration breakdown |
| `/ack ALERT_ID` | Acknowledge an alert |
| `/reflect TICKER` | Log post-trade reflection |

## Scoring Engine (SC1-SC8)

| Axis | Name | Method | Status |
|------|------|--------|--------|
| SC1 | Catalyst Timing | Deterministic | Implemented |
| SC2 | Clinical Data Strength | Hybrid | Manual/AI (Phase 2) |
| SC3 | Unmet Medical Need | Hybrid | Manual/AI (Phase 2) |
| SC4 | Competitive Landscape | Hybrid | Manual/AI (Phase 2) |
| SC5 | Financial Health | Deterministic | Implemented |
| SC6 | Liquidity | Deterministic | Implemented |
| SC7 | Risk/Reward | Deterministic | Implemented |
| SC8 | Macro/Sector | Hybrid | Manual/AI (Phase 2) |

## Scheduled Jobs

| Job | Schedule (SGT) | Description |
|-----|---------------|-------------|
| Morning Brief | 8:00 AM weekdays | Portfolio + catalysts + action items |
| Catalyst Alerts | 9:00 PM daily | T-7, T-3, T-1 countdown alerts |
| Price Check | Every 10 min (market hours) | Alert on >10% moves |
| Keepalive | Every 12 hours | Prevent Supabase auto-pause |
| False Negative Tracker | 10:30 PM weekdays | Track rejected candidates |

## Project Structure

```
strategy5x/
├── config.py          # Configuration and constants
├── db.py              # Supabase client wrapper
├── bot/
│   ├── main.py        # Bot entry point (python-telegram-bot v20+ async)
│   ├── formatters.py  # Telegram message formatting
│   └── handlers/      # Command handlers (10 commands)
├── scoring/
│   ├── engine.py      # SC1-SC8 scoring engine
│   ├── da_checks.py   # Devil's Advocate checks (6 deterministic checks)
│   └── constants.py   # Scoring curves and thresholds
├── jobs/              # Scheduled jobs (6 jobs via APScheduler)
├── data/
│   ├── market_data.py # yfinance wrapper with 15-min cache
│   ├── catalyst_calendar.py  # Catalyst date helpers
│   └── moomoo_sync.py        # CSV import (Phase 1) / API (Phase 2)
└── utils/
    ├── provenance.py  # Data source tagging ([FINANCE], [CALC], etc.)
    └── timezone.py    # SGT/UTC conversion helpers
```

## Devil's Advocate Checks

The DA system runs 6 deterministic checks on every scoring run:

1. **Hard Ban Check** — ticker against rules table bans
2. **Concentration Cap** — would position exceed 10% single-name cap?
3. **Margin Utilization** — would this push margin >40%?
4. **Cash Runway** — SC5 going concern flag (<6mo = BLOCK, <12mo = CAUTION)
5. **Duplicate Catalyst** — already holding same catalyst date?
6. **Max Positions** — would this exceed position limit?

Verdict aggregation: any BLOCK = overall BLOCK, else any CAUTION = overall CAUTION, else PROCEED.
