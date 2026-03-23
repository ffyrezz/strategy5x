#!/usr/bin/env bash
set -euo pipefail

echo "=== Strategy5x Setup ==="
echo ""

# 1. Create virtual environment
if [ ! -d ".venv" ]; then
  echo "[1/5] Creating virtual environment..."
  python3 -m venv .venv
else
  echo "[1/5] Virtual environment already exists."
fi

source .venv/bin/activate

# 2. Install dependencies
echo "[2/5] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "      Done."

# 3. Copy .env.example to .env if needed
if [ ! -f ".env" ]; then
  echo "[3/5] Creating .env from .env.example..."
  cp .env.example .env
  echo ""
  echo "  >>> IMPORTANT: Edit .env and fill in your credentials <<<"
  echo ""
  echo "  You need:"
  echo "    SUPABASE_URL     — from Supabase dashboard > Settings > API"
  echo "    SUPABASE_KEY     — anon/public key from same page"
  echo "    TELEGRAM_BOT_TOKEN — from @BotFather on Telegram"
  echo "    TELEGRAM_CHAT_ID   — send /start to your bot, then visit:"
  echo "      https://api.telegram.org/bot<TOKEN>/getUpdates"
  echo ""
else
  echo "[3/5] .env already exists, skipping copy."
fi

# Load .env for connection tests
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

# 4. Test Supabase connection
echo "[4/5] Testing Supabase connection..."
if [ -z "${SUPABASE_URL:-}" ] || [ "$SUPABASE_URL" = "https://your-project.supabase.co" ]; then
  echo "      SKIPPED — SUPABASE_URL not configured yet."
else
  python3 -c "
from supabase import create_client
import os
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
result = sb.table('positions').select('*', count='exact').limit(0).execute()
print(f'      OK — Supabase connected (positions table accessible).')
" 2>/dev/null || echo "      WARN — Could not connect to Supabase. Check your credentials."
fi

# 5. Test Telegram bot token
echo "[5/5] Testing Telegram bot..."
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ "$TELEGRAM_BOT_TOKEN" = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" ]; then
  echo "      SKIPPED — TELEGRAM_BOT_TOKEN not configured yet."
else
  BOT_INFO=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" 2>/dev/null)
  if echo "$BOT_INFO" | grep -q '"ok":true'; then
    BOT_NAME=$(echo "$BOT_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['username'])" 2>/dev/null)
    echo "      OK — Bot @${BOT_NAME} is valid."
  else
    echo "      WARN — Bot token invalid. Check TELEGRAM_BOT_TOKEN."
  fi
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Fill in .env with your credentials (if not done)"
echo "  2. Run: source .venv/bin/activate"
echo "  3. Test locally: python -m bot.main"
echo "  4. Set GitHub Actions secrets (Settings > Secrets):"
echo "     SUPABASE_URL, SUPABASE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"
echo "  5. Push to GitHub — workflows will start on schedule"
