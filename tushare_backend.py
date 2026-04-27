import os
import time
import logging
import tushare as ts
import pandas as pd

_pro = None
_token = None
_logger = logging.getLogger(__name__)
_TUSHARE_TIMEOUT_SECONDS = float(os.environ.get("TUSHARE_TIMEOUT_SECONDS", "12"))
_DEFAULT_HIST_RETRIES = int(os.environ.get("TUSHARE_HIST_RETRIES", "2"))
_UNIVERSE_CACHE_TTL_SECONDS = int(os.environ.get("SCAN_UNIVERSE_CACHE_TTL_SECONDS", "3600"))
_universe_cache = {"fetched_at": 0.0, "data": None}

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


def _get_universe_df(pro):
    now = time.time()
    global _universe_cache
    if (_universe_cache["data"] is not None
            and now - _universe_cache["fetched_at"] < _UNIVERSE_CACHE_TTL_SECONDS):
        return _universe_cache["data"].copy()

    df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,area,industry")
    df = df.rename(columns={"symbol": "code"})
    df = df[~df["name"].str.contains("ST|\\*ST|退", na=False)]
    df["industry"] = df["industry"].fillna("未分类")
    df["market_board"] = df["code"].map(_classify_market_board)
    df = df[["code", "name", "market_board", "industry"]].reset_index(drop=True)
    _universe_cache["data"] = df
    _universe_cache["fetched_at"] = now
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
