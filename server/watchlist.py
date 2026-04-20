import json
import os
from datetime import datetime

from data_fetcher import get_stock_hist
from strategy import compute_exit_signal

_WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "watchlist.json")
_memory_store = {"items": []}


def _load_watchlist():
    if os.path.exists(_WATCHLIST_PATH):
        try:
            with open(_WATCHLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _memory_store.update(data)
                return data
        except Exception:
            pass
    return _memory_store.copy()


def _save_watchlist(data):
    global _memory_store
    _memory_store = data.copy()
    try:
        with open(_WATCHLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_watchlist():
    return _load_watchlist()["items"]


def add_to_watchlist(code, name, entry_price, entry_date):
    data = _load_watchlist()
    if any(item["code"] == code for item in data["items"]):
        return False
    data["items"].append({
        "code": code,
        "name": name,
        "entry_price": entry_price,
        "entry_date": entry_date,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "exit_triggered": False,
        "latest_close": None,
        "pnl_pct": None,
    })
    _save_watchlist(data)
    return True


def remove_from_watchlist(code):
    data = _load_watchlist()
    data["items"] = [item for item in data["items"] if item["code"] != code]
    _save_watchlist(data)
    return True


def refresh_watchlist():
    data = _load_watchlist()
    alerts = []
    for item in data["items"]:
        df = get_stock_hist(item["code"], days=60)
        if df.empty or len(df) < 10:
            continue
        n = len(df) - 1
        was_triggered = item.get("exit_triggered", False)
        now_triggered = bool(compute_exit_signal(df, n))
        latest_close = round(float(df.loc[n, "close"]), 2)
        pnl = round((latest_close - item["entry_price"]) / item["entry_price"] * 100, 2) if item["entry_price"] > 0 else 0.0

        item["exit_triggered"] = now_triggered
        item["latest_close"] = latest_close
        item["pnl_pct"] = pnl

        if now_triggered and not was_triggered:
            alerts.append(item)

    _save_watchlist(data)
    return alerts


def get_alerts():
    data = _load_watchlist()
    return [item for item in data["items"] if item.get("exit_triggered", False)]
