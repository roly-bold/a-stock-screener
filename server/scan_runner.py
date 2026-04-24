import asyncio
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime

from data_fetcher import (
    _code_to_ts,
    get_broker_recommend,
    get_chip_perf,
    get_scan_universe_options,
    get_stock_hist,
    get_stock_universe,
)
from strategy import screen_stock

_STATUS_IDLE = "idle"
_STATUS_RUNNING = "running"
_STATUS_COMPLETE = "complete"
_STATUS_ERROR = "error"

_scan_status = _STATUS_IDLE
_cancel_flag = False
_subscribers: list[asyncio.Queue] = []
_latest_results: list[dict] = []
_latest_timestamp = ""
_last_error = ""
_latest_progress: dict | None = None
_current_scope = {"market_board": "全部板块", "industry": "全部行业"}
_current_run_id = ""
_loop: asyncio.AbstractEventLoop | None = None
_rate_lock = threading.Lock()
_api_calls = []
_logger = logging.getLogger(__name__)

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
_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "scan_history.json")
_MAX_HISTORY_RUNS = 20
_MAX_LOGS_PER_RUN = 180


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


def get_state():
    return {
        "status": _scan_status,
        "timestamp": _latest_timestamp,
        "results_count": len(_latest_results),
        "error": _last_error,
        "progress": _latest_progress,
        "scope": _current_scope.copy(),
        "run_id": _current_run_id,
    }


def get_strategy_params():
    return _current_strategy_params.copy()


def get_scan_options(market_board=None):
    options = get_scan_universe_options()
    if market_board and market_board not in ("全部板块", "全部市场", "全部"):
        filtered = get_stock_universe(market_board=market_board)
        industry_counts = (
            filtered.groupby("industry")
            .size()
            .sort_values(ascending=False)
            .items()
        )
        options["industries"] = [{"name": name, "count": int(count)} for name, count in industry_counts]
        options["total_count"] = int(len(filtered))
    else:
        options["total_count"] = int(sum(item["count"] for item in options["market_boards"]))
    return options


def _load_history():
    if os.path.exists(_HISTORY_PATH):
        try:
            with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            _logger.exception("读取扫描历史失败")
    return []


def _save_history(history):
    try:
        with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history[:_MAX_HISTORY_RUNS], f, ensure_ascii=False, indent=2)
    except Exception:
        _logger.exception("保存扫描历史失败")


def get_scan_history():
    return _load_history()


def _start_history_run(days, delay, strategy_params, scope):
    global _current_run_id
    run_id = uuid.uuid4().hex[:12]
    _current_run_id = run_id
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run = {
        "run_id": run_id,
        "status": _STATUS_RUNNING,
        "started_at": started_at,
        "finished_at": None,
        "days": days,
        "delay": delay,
        "scope": scope.copy(),
        "strategy": strategy_params.copy(),
        "signals_count": 0,
        "error": "",
        "logs": [{
            "type": "started",
            "timestamp": started_at,
            "message": f"开始扫描: {scope.get('market_board', '全部板块')} / {scope.get('industry', '全部行业')}",
        }],
    }
    history = [run] + [item for item in _load_history() if item.get("run_id") != run_id]
    _save_history(history)
    return run_id


def _append_history_event(event):
    if not _current_run_id:
        return
    history = _load_history()
    timestamp = event.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for run in history:
        if run.get("run_id") != _current_run_id:
            continue
        log = {
            "type": event.get("type", "log"),
            "timestamp": timestamp,
        }
        for key in ("phase", "current", "total", "percent", "message", "heartbeat", "pending"):
            if key in event:
                log[key] = event.get(key)
        run.setdefault("logs", []).append(log)
        run["logs"] = run["logs"][-_MAX_LOGS_PER_RUN:]
        break
    _save_history(history)


def _finish_history_run(status, signals_count=0, error=""):
    global _current_run_id
    if not _current_run_id:
        return
    history = _load_history()
    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for run in history:
        if run.get("run_id") != _current_run_id:
            continue
        run["status"] = status
        run["finished_at"] = finished_at
        run["signals_count"] = signals_count
        run["error"] = error
        break
    _save_history(history)
    _current_run_id = ""


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
    global _latest_progress
    if event.get("type") == "progress":
        payload = event.copy()
        payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _latest_progress = payload
        event = payload
    if event.get("type") in {"progress", "complete", "error", "cancelled"}:
        _append_history_event(event)
    if _loop:
        for q in _subscribers:
            _loop.call_soon_threadsafe(q.put_nowait, event)


_MAX_API_PER_MIN = 450


def _reserve_api_calls(count=1):
    global _api_calls
    while True:
        with _rate_lock:
            now = time.time()
            _api_calls = [t for t in _api_calls if now - t < 60]
            if len(_api_calls) + count <= _MAX_API_PER_MIN:
                _api_calls.extend([now] * count)
                return
            sleep_time = 60 - (now - _api_calls[0]) + 0.1 if _api_calls else 0.5
        time.sleep(max(0, sleep_time))


def _wait_rate():
    _reserve_api_calls()


def _fetch_one(code, name, days, delay, strategy_params):
    if _cancel_flag:
        return None
    if delay > 0:
        time.sleep(delay)
    _reserve_api_calls(2)
    try:
        df = get_stock_hist(code, days=days)
        if df.empty or len(df) < 30:
            return None
        signals = screen_stock(df, **strategy_params)
        for s in signals:
            s["code"] = code
            s["name"] = name
        return signals
    except Exception:
        _logger.exception("扫描股票失败: %s(%s)", name, code)
        return None


def _enrich_signals(signals):
    if not signals:
        return
    try:
        _reserve_api_calls()
        brokers = get_broker_recommend()
    except Exception:
        _logger.exception("加载券商推荐失败")
        brokers = {}
    for i, s in enumerate(signals):
        ts_code = _code_to_ts(s["code"])
        try:
            _reserve_api_calls()
            chip = get_chip_perf(ts_code)
        except Exception:
            _logger.exception("加载筹码数据失败: %s", ts_code)
            chip = None
        if chip:
            s["winner_rate"] = round(chip.get("winner_rate", 0), 2)
            s["weight_avg_cost"] = round(chip.get("weight_avg", 0), 2)
            s["cost_50pct"] = round(chip.get("cost_50pct", 0), 2)
        else:
            s["winner_rate"] = 0
            s["weight_avg_cost"] = 0
            s["cost_50pct"] = 0
        rec = brokers.get(s["code"], [])
        s["brokers"] = rec
        s["broker_count"] = len(rec)
        if (i + 1) % 10 == 0 or i == len(signals) - 1:
            _emit({"type": "progress", "phase": "enriching", "current": i + 1,
                   "total": len(signals), "percent": round((i + 1) / len(signals) * 100, 1)})


def _run_scan_thread(days, delay, strategy_params, scope):
    global _scan_status, _latest_results, _latest_timestamp, _current_strategy_params
    global _cancel_flag, _last_error, _latest_progress, _current_scope

    _current_strategy_params = strategy_params.copy()
    _current_scope = scope.copy()
    _cancel_flag = False
    _last_error = ""
    _latest_progress = None
    global _api_calls
    _api_calls = []
    max_workers = 20

    try:
        _start_history_run(days, delay, strategy_params, scope)
        _emit({"type": "progress", "phase": "listing", "current": 0, "total": 0, "percent": 0})
        stock_list = get_stock_universe(
            market_board=scope.get("market_board"),
            industry=scope.get("industry"),
        )
        total = len(stock_list)
        if total == 0:
            raise RuntimeError("所选板块范围内没有可扫描股票，请调整筛选条件。")
        _emit({"type": "progress", "phase": "fetching", "current": 0, "total": total, "percent": 0})

        results = []
        fetched = 0
        tasks = [(row["code"], row["name"]) for _, row in stock_list.iterrows()]

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch_one, code, name, days, delay, strategy_params): code
                       for code, name in tasks}
            pending = set(futures)
            while pending:
                if _cancel_flag:
                    pool.shutdown(wait=False, cancel_futures=True)
                    _scan_status = _STATUS_IDLE
                    _emit({"type": "cancelled"})
                    _finish_history_run("cancelled", signals_count=len(results))
                    _subscribers.clear()
                    return
                try:
                    future = next(as_completed(pending, timeout=5))
                except FuturesTimeoutError:
                    _emit({
                        "type": "progress",
                        "phase": "fetching",
                        "current": fetched,
                        "total": total,
                        "percent": round(fetched / total * 100, 1) if total else 0,
                        "heartbeat": True,
                        "pending": len(pending),
                    })
                    continue
                pending.remove(future)
                fetched += 1
                code = futures[future]
                try:
                    sigs = future.result()
                except Exception:
                    _logger.exception("线程任务失败: %s", code)
                    sigs = None
                if sigs:
                    results.extend(sigs)
                if fetched % 25 == 0 or fetched == total:
                    _emit({"type": "progress", "phase": "fetching", "current": fetched, "total": total,
                           "percent": round(fetched / total * 100, 1)})

        results.sort(key=lambda x: x["entry_date"], reverse=True)

        _emit({"type": "progress", "phase": "enriching", "current": 0, "total": len(results), "percent": 0})
        _enrich_signals(results)

        _add_pnl(results)

        with open(_RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        _latest_results = results
        _latest_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _scan_status = _STATUS_COMPLETE
        _latest_progress = {
            "type": "progress",
            "phase": "complete",
            "current": total,
            "total": total,
            "percent": 100,
            "updated_at": _latest_timestamp,
        }

        _emit({"type": "complete", "signals_count": len(results), "timestamp": _latest_timestamp})
        _finish_history_run(_STATUS_COMPLETE, signals_count=len(results))

        from server import watchlist
        try:
            alerts = watchlist.refresh_watchlist()
            if alerts:
                _emit({"type": "watchlist_alerts", "alerts": alerts})
        except Exception:
            pass

        _subscribers.clear()

    except Exception as e:
        _last_error = str(e) or "扫描失败"
        _scan_status = _STATUS_ERROR
        _logger.exception("扫描任务失败")
        _emit({"type": "error", "message": _last_error})
        _finish_history_run(_STATUS_ERROR, error=_last_error)
        _subscribers.clear()


def start_scan(days=120, delay=0.05, strategy_params=None, scope=None):
    global _scan_status
    if _scan_status == _STATUS_RUNNING:
        return False
    _scan_status = _STATUS_RUNNING
    params = strategy_params or _default_strategy_params.copy()
    scan_scope = scope or _current_scope.copy()
    t = threading.Thread(target=_run_scan_thread, args=(days, delay, params, scan_scope), daemon=True)
    t.start()
    return True


def stop_scan():
    global _cancel_flag, _scan_status
    if _scan_status != _STATUS_RUNNING:
        return False
    _cancel_flag = True
    return True
