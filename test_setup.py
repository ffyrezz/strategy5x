"""
Strategy 5.x — Setup Verification Script
Run this after configuring .env to verify all connections work.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check_env():
    """Check all required environment variables are set."""
    required = ['SUPABASE_URL', 'SUPABASE_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        return False
    print("✅ All environment variables set")
    return True

def check_supabase():
    """Test Supabase connection and verify tables exist."""
    from supabase import create_client
    try:
        client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
        
        # Check key tables
        tables = ['positions', 'rules', 'scoring_runs', 'alerts', 'pipeline_candidates', 'precommitment_plans']
        for table in tables:
            try:
                result = client.table(table).select('*').limit(1).execute()
                count = len(result.data)
                print(f"  ✅ {table}: accessible ({count} rows)")
            except Exception as e:
                print(f"  ❌ {table}: {str(e)[:100]}")
                return False
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

def check_telegram():
    """Test Telegram bot can send messages."""
    import httpx
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    # Check bot identity
    r = httpx.get(f"https://api.telegram.org/bot{token}/getMe")
    if not r.json().get('ok'):
        print(f"❌ Telegram bot token invalid: {r.json()}")
        return False
    
    bot_name = r.json()['result']['username']
    print(f"  ✅ Bot: @{bot_name}")
    
    # Try sending
    r2 = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
        "chat_id": chat_id,
        "text": "🟢 Strategy 5.x — Setup verification complete!\n\nAll systems connected. Bot is ready.",
    })
    if r2.json().get('ok'):
        print(f"  ✅ Message sent to chat {chat_id}")
        return True
    else:
        print(f"  ⚠️  Message send failed: {r2.json().get('description')}")
        print(f"     → Have you opened @{bot_name} on Telegram and sent /start?")
        return False

def check_market_data():
    """Test yfinance can fetch prices."""
    import yfinance as yf
    try:
        ticker = yf.Ticker("AXSM")
        price = ticker.fast_info.get('lastPrice') or ticker.info.get('currentPrice')
        if price:
            print(f"  ✅ yfinance: AXSM = ${price:.2f}")
            return True
        else:
            print("  ⚠️  yfinance: no price returned (market may be closed)")
            return True  # Not a failure
    except Exception as e:
        print(f"  ❌ yfinance failed: {e}")
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("Strategy 5.x — Setup Verification")
    print("=" * 50)
    
    results = {}
    
    print("\n1. Environment Variables")
    results['env'] = check_env()
    
    if results['env']:
        print("\n2. Supabase Database")
        results['supabase'] = check_supabase()
        
        print("\n3. Telegram Bot")
        results['telegram'] = check_telegram()
        
        print("\n4. Market Data (yfinance)")
        results['market'] = check_market_data()
    
    print("\n" + "=" * 50)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")
    
    if all(results.values()):
        print("🟢 All systems go! You can start the bot with: python -m bot.main")
    else:
        print("🔴 Some checks failed. Fix the issues above before proceeding.")
    print("=" * 50)
