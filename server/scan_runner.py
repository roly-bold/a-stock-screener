import asyncio
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from data_fetcher import get_stock_list, get_stock_hist
from strategy import screen_stock

_STATUS_IDLE = "idle"
_STATUS_RUNNING = "running"
_STATUS_COMPLETE = "complete"

_scan_status = _STATUS_IDLE
_cancel_flag = False
_subscribers: list[asyncio.Queue] = []
_latest_results: list[dict] = []
_latest_timestamp = ""
_loop: asyncio.AbstractEventLoop | None = None

_default_strategy_params = {
    "vol_ma_window": 20,
    "vol_ratio_threshold": 2.0,
    "rise_threshold": 9.5,
    "cons_min_days": 3,
    "cons_max_days": 15,
    "vol_shrink_ratio": 0.5,
}
_current_strategy_params = _default_strategy_params.copy()

_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "results.json")


def _add_pnl(signals):
    for s in signals:
        if s["entry_price"] > 0:
            s["pnl_pct"] = round((s["latest_close"] - s["entry_price"]) / s["entry_price"] * 100, 2)
        else:
            s["pnl_pct"] = 0.0


def _load_cached_results():
    global _latest_results, _latest_timestamp
    if os.path.exists(_RESULTS_PATH):
        with open(_RESULTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _add_pnl(data)
        _latest_results = data
        mtime = os.path.getmtime(_RESULTS_PATH)
        _latest_timestamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")


def get_status():
    return _scan_status


def get_results():
    if not _latest_results:
        _load_cached_results()
    return _latest_results, _latest_timestamp


def get_strategy_params():
    return _current_strategy_params.copy()


def set_loop(loop):
    global _loop
    _loop = loop


def create_queue():
    q = asyncio.Queue()
    _subscribers.append(q)
    return q


def remove_queue(q):
    if q in _subscribers:
        _subscribers.remove(q)


def _emit(event: dict):
    if _loop:
        for q in _subscribers:
            _loop.call_soon_threadsafe(q.put_nowait, event)


def _fetch_one(code, name, days, strategy_params):
    if _cancel_flag:
        return None
    df = get_stock_hist(code, days=days)
    if df.empty or len(df) < 30:
        return None
    signals = screen_stock(df, **strategy_params)
    for s in signals:
        s["code"] = code
        s["name"] = name
    return signals


def _run_scan_thread(days, delay, strategy_params):
    global _scan_status, _latest_results, _latest_timestamp, _current_strategy_params, _cancel_flag

    _current_strategy_params = strategy_params.copy()
    _cancel_flag = False
    max_workers = 10

    try:
        _emit({"type": "progress", "phase": "listing", "current": 0, "total": 0, "percent": 0})
        stock_list = get_stock_list()
        total = len(stock_list)
        _emit({"type": "progress", "phase": "fetching", "current": 0, "total": total, "percent": 0})

        results = []
        fetched = 0
        tasks = [(row["code"], row["name"]) for _, row in stock_list.iterrows()]

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch_one, code, name, days, strategy_params): code
                       for code, name in tasks}
            for future in as_completed(futures):
                if _cancel_flag:
                    pool.shutdown(wait=False, cancel_futures=True)
                    _scan_status = _STATUS_IDLE
                    _emit({"type": "cancelled"})
                    _subscribers.clear()
                    return
                fetched += 1
                sigs = future.result()
                if sigs:
                    results.extend(sigs)
                if fetched % 50 == 0:
                    _emit({"type": "progress", "phase": "fetching", "current": fetched, "total": total,
                           "percent": round(fetched / total * 100, 1)})

        results.sort(key=lambda x: x["entry_date"], reverse=True)
        _add_pnl(results)

        with open(_RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        _latest_results = results
        _latest_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _scan_status = _STATUS_COMPLETE

        _emit({"type": "complete", "signals_count": len(results), "timestamp": _latest_timestamp})

        from server import watchlist
        try:
            alerts = watchlist.refresh_watchlist()
            if alerts:
                _emit({"type": "watchlist_alerts", "alerts": alerts})
        except Exception:
            pass

        _subscribers.clear()

    except Exception as e:
        _scan_status = _STATUS_IDLE
        _emit({"type": "error", "message": str(e)})
        _subscribers.clear()


def start_scan(days=120, delay=0.05, strategy_params=None):
    global _scan_status
    if _scan_status == _STATUS_RUNNING:
        return False
    _scan_status = _STATUS_RUNNING
    params = strategy_params or _default_strategy_params.copy()
    t = threading.Thread(target=_run_scan_thread, args=(days, delay, params), daemon=True)
    t.start()
    return True


def stop_scan():
    global _cancel_flag, _scan_status
    if _scan_status != _STATUS_RUNNING:
        return False
    _cancel_flag = True
    return True
