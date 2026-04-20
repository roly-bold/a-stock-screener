"""用模拟数据测试选股策略逻辑"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
from strategy import screen_stock, check_first_leg, check_consolidation, check_second_breakout

np.random.seed(42)


def make_test_data():
    """构造确定性模拟数据：强力起爆→缩量洗盘→二次突破"""
    dates = pd.bdate_range("2026-01-05", periods=90)
    records = []

    for i in range(30):
        records.append({
            "open": round(10.0 + 0.05 * (i % 3), 2),
            "close": round(10.0 + 0.05 * ((i + 1) % 3) + 0.02, 2),
            "high": round(10.0 + 0.1 * (i % 3) + 0.08, 2),
            "low": round(10.0 - 0.03, 2),
            "volume": 1000000,
        })
    records[-1]["close"] = 10.05
    records[-1]["high"] = 10.12
    records[-1]["low"] = 10.02
    records[-1]["open"] = 10.03

    breakout_open = 10.10
    breakout_close = 11.11
    breakout_high = 11.15
    breakout_low = 10.08
    breakout_vol = 5000000
    records.append({
        "open": breakout_open, "close": breakout_close,
        "high": breakout_high, "low": breakout_low,
        "volume": breakout_vol,
    })

    support = breakout_open
    for i in range(7):
        c = round(breakout_close - 0.15 - 0.05 * i, 2)
        c = max(c, support + 0.10)
        o = round(c + 0.03, 2)
        records.append({
            "open": o, "close": c,
            "high": round(max(o, c) + 0.05, 2),
            "low": round(min(o, c) - 0.03, 2),
            "volume": int(breakout_vol * 0.25),
        })

    prev_close = records[-1]["close"]
    entry_open = round(prev_close + 0.05, 2)
    entry_close = round(breakout_high + 0.03, 2)
    records.append({
        "open": entry_open, "close": entry_close,
        "high": round(entry_close + 0.05, 2),
        "low": round(entry_open - 0.02, 2),
        "volume": int(breakout_vol * 0.45),
    })

    for i in range(51):
        base = entry_close + 0.15 * (i + 1)
        records.append({
            "open": round(base, 2), "close": round(base + 0.05, 2),
            "high": round(base + 0.10, 2), "low": round(base - 0.03, 2),
            "volume": 2000000,
        })

    df = pd.DataFrame(records)
    df.insert(0, "date", dates[:len(df)])
    df["amount"] = df["volume"] * df["close"]
    df["pct_change"] = df["close"].pct_change() * 100
    df["amplitude"] = ((df["high"] - df["low"]) / df["close"].shift(1) * 100).round(2)
    df["change"] = df["close"] - df["close"].shift(1)
    df["turnover"] = 0
    df = df.dropna().reset_index(drop=True)
    return df


def find_breakout_idx(df):
    return df["pct_change"].idxmax()


def test_first_leg():
    df = make_test_data()
    idx = find_breakout_idx(df)
    passed, pivot_high, support_price, breakout_vol = check_first_leg(df, idx)
    print(f"起爆检测: passed={passed}, pivot={pivot_high}, support={support_price}")
    assert passed and pivot_high > 11.0


def test_consolidation():
    df = make_test_data()
    idx = find_breakout_idx(df)
    _, pivot, support, bk_vol = check_first_leg(df, idx)
    ok, cons_end = check_consolidation(df, idx, support, bk_vol)
    print(f"洗盘检测: ok={ok}, cons_end={cons_end}")
    assert ok


def test_second_breakout():
    df = make_test_data()
    idx = find_breakout_idx(df)
    _, pivot, support, bk_vol = check_first_leg(df, idx)
    _, cons_end = check_consolidation(df, idx, support, bk_vol)
    ok, bk_idx = check_second_breakout(df, cons_end, pivot)
    print(f"突破检测: ok={ok}, bk_idx={bk_idx}")
    assert ok


def test_full_screen():
    df = make_test_data()
    signals = screen_stock(df)
    print(f"完整策略: {len(signals)} 个信号")
    for s in signals:
        print(f"  起爆={s['breakout_date']}, 突破={s['entry_date']}, 买入={s['entry_price']}")
    assert len(signals) >= 1


if __name__ == "__main__":
    test_first_leg()
    test_consolidation()
    test_second_breakout()
    test_full_screen()
    print("\n所有测试通过!")
