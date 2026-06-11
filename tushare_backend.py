import os
import json
import time
import logging
import tushare as ts
import pandas as pd

_pro = None
_token = None
_logger = logging.getLogger(__name__)

# ============ 修复 1：连接超时从 12 秒放宽到 30 秒 ============
# Railway（美国）到 Tushare（中国）是跨境链路，12 秒经常不够建立连接。
# 仍可通过环境变量 TUSHARE_TIMEOUT_SECONDS 覆盖。
_TUSHARE_TIMEOUT_SECONDS = float(os.environ.get("TUSHARE_TIMEOUT_SECONDS", "30"))

_DEFAULT_HIST_RETRIES = int(os.environ.get("TUSHARE_HIST_RETRIES", "2"))
_UNIVERSE_CACHE_TTL_SECONDS = int(os.environ.get("SCAN_UNIVERSE_CACHE_TTL_SECONDS", "3600"))
_universe_cache = {"fetched_at": 0.0, "data": None}

# ============ 修复 2：股票列表磁盘缓存文件路径 ============
# 股票列表一天才变一次，落盘保存后，即使 Tushare 临时连不上，
# 也能退回用上一次成功拉取的列表，定时扫描不会再因此整体失败。
_UNIVERSE_DISK_CACHE_PATH = os.path.join(os.path.dirname(__file__), "universe_cache.json")

# ============ 修复 3：stock_basic 重试次数与等待间隔 ============
_UNIVERSE_RETRIES = int(os.environ.get("TUSHARE_UNIVERSE_RETRIES", "3"))

_TUSHARE_RENAME = {
    "trade_date": "date", "open": "open", "close": "close",
    "high": "high", "low": "low", "vol": "volume",
    "amount": "amount", "pct_chg": "pct_change", "change": "change"
}


def init(t):
    global _token, _pro
    _token = t
    _pro = ts.pro_api(_token, timeout=_TUSHARE_TIMEOUT_SECONDS)


def _get_pro():
    global _pro
    if _pro is not None:
        return _pro
    if not _token:
        raise RuntimeError("Tushare backend 未初始化，请先配置 token")
    _pro = ts.pro_api(_token, timeout=_TUSHARE_TIMEOUT_SECONDS)
    return _pro


def _normalize_hist_df(df):
    df = df.rename(columns=_TUSHARE_RENAME)
    keep = [v for v in _TUSHARE_RENAME.values() if v in df.columns]
    df = df[keep]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    if "pct_change" not in df.columns and "close" in df.columns:
        df["pct_change"] = df["close"].pct_change() * 100
    if "volume" in df.columns:
        df["volume"] = df["volume"].astype(float)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _load_universe_disk_cache():
    """从磁盘读取上一次成功保存的股票列表，读不到返回 None"""
    try:
        if os.path.exists(_UNIVERSE_DISK_CACHE_PATH):
            with open(_UNIVERSE_DISK_CACHE_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
            df = pd.DataFrame(payload["data"])
            if not df.empty:
                return df, payload.get("fetched_at", 0.0)
    except Exception:
        _logger.exception("读取股票列表磁盘缓存失败")
    return None, 0.0


def _save_universe_disk_cache(df, fetched_at):
    """把股票列表写入磁盘，供下次拉取失败时兜底使用"""
    try:
        payload = {
            "fetched_at": fetched_at,
            "saved_date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": df.to_dict(orient="records"),
        }
        with open(_UNIVERSE_DISK_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        _logger.exception("保存股票列表磁盘缓存失败")


def _fetch_stock_basic_with_retry(pro):
    """
    ============ 修复 3：给 stock_basic 加重试 ============
    原代码只调用一次，跨境网络抖动时直接导致整个扫描任务失败。
    现在最多重试 _UNIVERSE_RETRIES 次，失败后等待 5/15/30 秒再试。
    """
    last_exc = None
    waits = [5, 15, 30]
    for attempt in range(_UNIVERSE_RETRIES):
        try:
            df = pro.stock_basic(
                exchange="", list_status="L",
                fields="ts_code,symbol,name,area,industry",
            )
            if df is not None and not df.empty:
                return df
            last_exc = RuntimeError("stock_basic 返回空数据")
        except Exception as exc:
            last_exc = exc
            _logger.warning(
                "拉取股票列表失败，第 %s/%s 次: %s",
                attempt + 1, _UNIVERSE_RETRIES, exc,
            )
        if attempt < _UNIVERSE_RETRIES - 1:
            time.sleep(waits[min(attempt, len(waits) - 1)])
    raise last_exc


def _get_universe_df(pro):
    now = time.time()
    global _universe_cache

    # 1. 内存缓存仍然新鲜，直接用
    if (_universe_cache["data"] is not None
            and now - _universe_cache["fetched_at"] < _UNIVERSE_CACHE_TTL_SECONDS):
        return _universe_cache["data"].copy()

    # 2. 尝试从 Tushare 拉最新列表（带重试）
    try:
        df = _fetch_stock_basic_with_retry(pro)
    except Exception as exc:
        # ============ 修复 2：拉取失败时退回旧缓存，而不是让整个扫描挂掉 ============
        # 优先用过期的内存缓存，其次用磁盘缓存。股票列表一天才变一次，
        # 用昨天的列表扫描完全没问题。
        if _universe_cache["data"] is not None:
            _logger.warning("拉取股票列表失败，改用内存中的旧缓存继续扫描: %s", exc)
            return _universe_cache["data"].copy()
        disk_df, disk_fetched_at = _load_universe_disk_cache()
        if disk_df is not None:
            _logger.warning("拉取股票列表失败，改用磁盘旧缓存继续扫描: %s", exc)
            _universe_cache["data"] = disk_df
            _universe_cache["fetched_at"] = disk_fetched_at
            return disk_df.copy()
        # 内存、磁盘都没有缓存，只能报错
        raise

    df = df.rename(columns={"symbol": "code"})
    df = df[~df["name"].str.contains("ST|\\*ST|退", na=False)]
    df["industry"] = df["industry"].fillna("未分类")
    df["market_board"] = df["code"].map(_classify_market_board)
    df = df[["code", "name", "market_board", "industry"]].reset_index(drop=True)
    _universe_cache["data"] = df
    _universe_cache["fetched_at"] = now
    # 拉取成功后顺手写入磁盘，供以后兜底
    _save_universe_disk_cache(df, now)
    return df.copy()


def _classify_market_board(code):
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith("688"):
        return "科创板"
    if code.startswith(("600", "601", "603", "605")):
        return "沪主板"
    if code.startswith(("000", "001", "002", "003")):
        return "深主板"
    if code.startswith(("4", "8", "9")):
        return "北交所"
    return "其他"


_SUPPORTED_MARKET_BOARDS = ("沪主板", "深主板", "创业板")


def get_stock_hist(symbol, days=120, retries=None):
    if retries is None:
        retries = _DEFAULT_HIST_RETRIES
    end_date = pd.Timestamp.now().strftime("%Y%m%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days * 2)).strftime("%Y%m%d")
    ts_code = _code_to_ts(symbol)
    pro = _get_pro()

    for attempt in range(retries):
        try:
            df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return pd.DataFrame()

            adj = pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if not adj.empty:
                df = df.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
                df["adj_factor"] = df["adj_factor"].ffill().bfill()
                factor = df["adj_factor"] / df["adj_factor"].iloc[-1]
                for col in ["open", "high", "low", "close"]:
                    df[col] = df[col] * factor
                df = df.drop(columns=["adj_factor"])

            df = _normalize_hist_df(df)
            if len(df) >= 10:
                return df.tail(days).reset_index(drop=True)
        except Exception as exc:
            if attempt < retries - 1:
                _logger.warning("获取 %s 历史数据失败，第 %s/%s 次重试: %s", ts_code, attempt + 1, retries, exc)
                time.sleep(0.5 * (attempt + 1))
            else:
                _logger.warning("获取 %s 历史数据失败，已放弃: %s", ts_code, exc)
    return pd.DataFrame()


def get_stock_universe(market_board=None, industry=None, supported_only=True):
    pro = _get_pro()
    df = _get_universe_df(pro)
    if supported_only:
        df = df[df["market_board"].isin(_SUPPORTED_MARKET_BOARDS)]
    if market_board and market_board not in ("全部板块", "全部市场", "全部"):
        df = df[df["market_board"] == market_board]
    if industry and industry not in ("全部行业", "全部"):
        df = df[df["industry"] == industry]
    return df.reset_index(drop=True)


def get_scan_universe_options():
    df = get_stock_universe()
    market_counts = (
        df.groupby("market_board").size().sort_values(ascending=False).items()
    )
    industry_counts = (
        df.groupby("industry").size().sort_values(ascending=False).items()
    )
    return {
        "market_boards": [{"name": name, "count": int(count)} for name, count in market_counts],
        "industries": [{"name": name, "count": int(count)} for name, count in industry_counts],
    }


def get_stock_list():
    return get_stock_universe()[["code", "name"]].reset_index(drop=True)


def get_chip_perf(ts_code, trade_date=None):
    pro = _get_pro()
    try:
        if trade_date:
            df = pro.cyq_perf(ts_code=ts_code, trade_date=trade_date)
        else:
            end = pd.Timestamp.now().strftime("%Y%m%d")
            start = (pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y%m%d")
            df = pro.cyq_perf(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        return df.iloc[-1].to_dict()
    except Exception:
        return None


def get_broker_recommend(month=None):
    if not month:
        month = pd.Timestamp.now().strftime("%Y%m")
    pro = _get_pro()
    try:
        df = pro.broker_recommend(month=month)
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            code = _ts_to_code(row["ts_code"])
            result.setdefault(code, []).append(row["broker"])
        return result
    except Exception:
        return {}


def _code_to_ts(code):
    if code[0] in ("0", "3"):
        return f"{code}.SZ"
    return f"{code}.SH"


def _ts_to_code(ts_code):
    return ts_code.split(".")[0]
