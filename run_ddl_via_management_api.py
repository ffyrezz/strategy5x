"""
Run DDL via Supabase Management API.
Requires: SUPABASE_ACCESS_TOKEN (from supabase.com dashboard > account > access tokens)
"""
import httpx
import sys
import os

PROJECT_REF = "nwkhsezifgmdckefbljl"

# Management API uses a personal access token, not the service role key
# The user would need to generate one at https://supabase.com/dashboard/account/tokens

def run_sql(token: str, sql: str):
    """Execute SQL via the Supabase Management API."""
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = httpx.post(url, headers=headers, json={"query": sql}, timeout=60)
    return response

if __name__ == "__main__":
    token = os.getenv("SUPABASE_ACCESS_TOKEN") or input("Enter your Supabase access token: ")
    
    ddl_files = [
        "supabase/001_week1_tables.sql",
        "supabase/002_week2_tables.sql",
        "supabase/003_week3_tables.sql",
        "supabase/004_views.sql",
        "supabase/005_seed_current_portfolio.sql",
    ]
    
    for filepath in ddl_files:
        filename = os.path.basename(filepath)
        with open(filepath, 'r') as f:
            sql = f.read()
        
        print(f"Running {filename}...", end=" ")
        r = run_sql(token, sql)
        if r.status_code == 200 or r.status_code == 201:
            print("✅")
        else:
            print(f"❌ {r.status_code}: {r.text[:200]}")
    
    print("\nDone!")
