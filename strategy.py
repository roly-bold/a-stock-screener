import numpy as np
import pandas as pd


def check_first_leg(df, idx, vol_ma_window=20, vol_ratio_threshold=2.0, rise_threshold=9.5):
    """第一阶段：强力起爆检测
    - 当日涨幅 >= rise_threshold
    - 成交量 >= vol_ma_window日均量的 vol_ratio_threshold 倍
    返回 (是否满足, pivot_high, 起爆日开盘价/最低价, 起爆日成交量)
    """
    if idx < vol_ma_window:
        return False, None, None, None

    pct = df.loc[idx, "pct_change"]
    vol = df.loc[idx, "volume"]
    vol_ma = df.loc[idx - vol_ma_window:idx - 1, "volume"].mean()

    if pct >= rise_threshold and vol >= vol_ma * vol_ratio_threshold:
        pivot_high = df.loc[idx, "high"]
        support_price = min(df.loc[idx, "open"], df.loc[idx, "low"])
        return True, pivot_high, support_price, vol

    return False, None, None, None


def check_consolidation(df, breakout_idx, support_price, breakout_vol,
                        min_days=3, max_days=15, vol_shrink_ratio=0.5,
                        shrink_days=3, warmup_days=2):
    """第二阶段：缩量洗盘检测
    - 3~15个交易日内整理
    - 跳过前warmup_days天（涨停后消化期），之后至少有shrink_days天连续缩量
    - 缩量期成交量 < 起爆日成交量的 vol_shrink_ratio
    - 股价不破起爆日开盘价/最低价
    - K线实体收窄（波动率收敛）
    返回 (是否满足, 整理结束索引)
    """
    n = len(df)

    for end_offset in range(min_days, max_days + 1):
        cons_end = breakout_idx + end_offset
        if cons_end >= n:
            break

        cons_slice = df.loc[breakout_idx + 1:cons_end]

        if cons_slice["low"].min() < support_price:
            continue

        warmup_end = breakout_idx + warmup_days
        if warmup_end >= cons_end:
            continue

        shrink_slice = df.loc[warmup_end + 1:cons_end]
        if len(shrink_slice) < shrink_days:
            continue

        shrink_vol = shrink_slice["volume"].mean()
        if shrink_vol >= breakout_vol * vol_shrink_ratio:
            continue

        bodies = (shrink_slice["close"] - shrink_slice["open"]).abs()
        pre_bodies = (df.loc[max(breakout_idx - 5, 0):breakout_idx - 1, "close"]
                      - df.loc[max(breakout_idx - 5, 0):breakout_idx - 1, "open"]).abs()
        if len(pre_bodies) > 0 and len(bodies) > 0 and bodies.mean() > pre_bodies.mean() * 2.0:
            continue

        return True, cons_end

    return False, None


def check_second_breakout(df, cons_end_idx, pivot_high):
    """第三阶段：二次突破检测
    - 收盘价站上 pivot_high
    - 成交量 > 前一日成交量
    返回 (是否满足, 突破日索引)
    """
    n = len(df)
    look_ahead = min(cons_end_idx + 10, n)

    for i in range(cons_end_idx + 1, look_ahead):
        if i >= n:
            break
        close = df.loc[i, "close"]
        vol = df.loc[i, "volume"]
        prev_vol = df.loc[i - 1, "volume"]

        if close > pivot_high and vol > prev_vol:
            return True, i

    return False, None


def compute_exit_signal(df, idx, sma_window=5):
    """出场逻辑：收盘价跌破SMA5"""
    if idx < sma_window:
        return False
    sma = df.loc[idx - sma_window + 1:idx, "close"].mean()
    return df.loc[idx, "close"] < sma


def screen_stock(df, vol_ma_window=20, vol_ratio_threshold=2.0,
                 rise_threshold=9.5, cons_min_days=3, cons_max_days=15,
                 vol_shrink_ratio=0.5):
    """对单只股票执行完整选股策略，返回符合条件的信号列表"""
    if len(df) < vol_ma_window + cons_max_days + 10:
        return []

    signals = []
    n = len(df)

    for i in range(vol_ma_window, n - cons_min_days):
        passed, pivot_high, support_price, breakout_vol = check_first_leg(
            df, i, vol_ma_window, vol_ratio_threshold, rise_threshold
        )
        if not passed:
            continue

        cons_ok, cons_end = check_consolidation(
            df, i, support_price, breakout_vol,
            cons_min_days, cons_max_days, vol_shrink_ratio
        )
        if not cons_ok:
            continue

        bk_ok, bk_idx = check_second_breakout(df, cons_end, pivot_high)
        if not bk_ok:
            continue

        signals.append({
            "breakout_date": df.loc[i, "date"].strftime("%Y-%m-%d"),
            "pivot_high": round(float(pivot_high), 2),
            "support_price": round(float(support_price), 2),
            "breakout_vol": int(breakout_vol),
            "consolidation_end": df.loc[cons_end, "date"].strftime("%Y-%m-%d"),
            "entry_date": df.loc[bk_idx, "date"].strftime("%Y-%m-%d"),
            "entry_price": round(float(df.loc[bk_idx, "close"]), 2),
            "entry_vol": int(df.loc[bk_idx, "volume"]),
            "latest_date": df.loc[n - 1, "date"].strftime("%Y-%m-%d"),
            "latest_close": round(float(df.loc[n - 1, "close"]), 2),
            "exit_triggered": bool(compute_exit_signal(df, n - 1)),
        })

        i = bk_idx

    return signals
