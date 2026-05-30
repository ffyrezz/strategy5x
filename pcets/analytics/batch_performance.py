"""PCETS Batch Performance Analytics
Reads master_backtest_b1_b11.csv and produces summary stats.
Run: python pcets/analytics/batch_performance.py
"""
import pandas as pd
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), '../backtests/master_backtest_b1_b11.csv')

def load_data():
    df = pd.read_csv(CSV_PATH)
    df['r_t7'] = pd.to_numeric(df['r_t7'], errors='coerce')
    df['win'] = df['r_t7'] > 0
    df['material_loss'] = df['r_t7'] < -5.0
    df['big_win'] = df['r_t7'] >= 15.0
    return df

def overall_stats(df):
    print('=== PCETS B1-B11 Overall Stats ===')
    print(f'Total BUY signals: {len(df)}')
    print(f'Win rate (T+7 > 0): {df["win"].mean():.1%}')
    print(f'Mean T+7 return: {df["r_t7"].mean():.2f}%')
    print(f'Median T+7 return: {df["r_t7"].median():.2f}%')
    print(f'Big wins (>=15%): {df["big_win"].sum()}')
    print(f'Material losses (<-5%): {df["material_loss"].sum()}')
    print()

def batch_stats(df):
    print('=== By Batch ===')
    stats = df.groupby('batch').agg(
        n=('r_t7', 'count'),
        win_rate=('win', 'mean'),
        mean_t7=('r_t7', 'mean'),
        median_t7=('r_t7', 'median')
    ).round(2)
    print(stats.to_string())
    print()

def sc_stats(df):
    print('=== By SC Score ===')
    stats = df.groupby('sc').agg(
        n=('r_t7', 'count'),
        win_rate=('win', 'mean'),
        mean_t7=('r_t7', 'mean'),
        best=('r_t7', 'max'),
        worst=('r_t7', 'min')
    ).round(2)
    print(stats.to_string())
    print()

def top_wins_losses(df, n=10):
    print(f'=== Top {n} Wins ===')
    print(df.nlargest(n, 'r_t7')[['ticker', 'batch', 'sc', 'r_t7', 'catalyst']].to_string(index=False))
    print()
    print(f'=== Top {n} Losses ===')
    print(df.nsmallest(n, 'r_t7')[['ticker', 'batch', 'sc', 'r_t7', 'catalyst']].to_string(index=False))

if __name__ == '__main__':
    df = load_data()
    overall_stats(df)
    batch_stats(df)
    sc_stats(df)
    top_wins_losses(df)
