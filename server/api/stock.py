from fastapi import APIRouter, Query

from data_fetcher import get_stock_list, get_stock_hist
from strategy import screen_stock
from server.models import StockHistoryBar, StockSearchResult

router = APIRouter(prefix="/api/stock", tags=["stock"])

_stock_list_cache = None


def _get_stock_list_cached():
    global _stock_list_cache
    if _stock_list_cache is None:
        _stock_list_cache = get_stock_list()
    return _stock_list_cache


@router.get("/search")
def search_stock(q: str = Query("", min_length=1)):
    sl = _get_stock_list_cached()
    q_lower = q.lower()
    mask = sl["code"].str.startswith(q) | sl["name"].str.contains(q, case=False, na=False)
    matches = sl[mask].head(20)
    return {"results": [StockSearchResult(code=r["code"], name=r["name"]) for _, r in matches.iterrows()]}


@router.get("/{code}/history")
def get_history(code: str, days: int = Query(120, ge=30, le=500)):
    df = get_stock_hist(code, days=days)
    if df.empty:
        return {"code": code, "name": "", "days": 0, "data": []}

    name = ""
    try:
        sl = _get_stock_list_cached()
        match = sl[sl["code"] == code]
        if not match.empty:
            name = match.iloc[0]["name"]
    except Exception:
        pass

    bars = []
    for _, row in df.iterrows():
        bars.append(StockHistoryBar(
            date=row["date"].strftime("%Y-%m-%d"),
            open=round(float(row["open"]), 2),
            close=round(float(row["close"]), 2),
            high=round(float(row["high"]), 2),
            low=round(float(row["low"]), 2),
            volume=round(float(row["volume"]), 0),
            pct_change=round(float(row["pct_change"]), 2),
        ))

    return {"code": code, "name": name, "days": len(bars), "data": bars}


@router.get("/{code}/signals")
def get_signals(code: str, days: int = Query(120, ge=30, le=500),
                vol_ma_window: int = Query(20), vol_ratio_threshold: float = Query(2.0),
                rise_threshold: float = Query(9.5), cons_min_days: int = Query(3),
                cons_max_days: int = Query(15), vol_shrink_ratio: float = Query(0.5)):
    df = get_stock_hist(code, days=days)
    if df.empty:
        return {"code": code, "name": "", "signals": []}

    name = ""
    try:
        sl = _get_stock_list_cached()
        match = sl[sl["code"] == code]
        if not match.empty:
            name = match.iloc[0]["name"]
    except Exception:
        pass

    signals = screen_stock(df, vol_ma_window=vol_ma_window, vol_ratio_threshold=vol_ratio_threshold,
                           rise_threshold=rise_threshold, cons_min_days=cons_min_days,
                           cons_max_days=cons_max_days, vol_shrink_ratio=vol_shrink_ratio)
    for s in signals:
        s["code"] = code
        s["name"] = name
        if s["entry_price"] > 0:
            s["pnl_pct"] = round((s["latest_close"] - s["entry_price"]) / s["entry_price"] * 100, 2)
        else:
            s["pnl_pct"] = 0.0

    return {"code": code, "name": name, "signals": signals}
