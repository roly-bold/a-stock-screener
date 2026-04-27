import logging
import time
import pandas as pd
from ifind_client import IFindClient

_logger = logging.getLogger(__name__)
_client = None

_IFIND_HIST_RENAME = {
    "time": "date", "open": "open", "high": "high",
    "low": "low", "close": "close", "volume": "volume",
    "amount": "amount", "pctChange": "pct_change",
}
_IFIND_BASIC_RENAME = {
    "stockCode": "code", "stockName": "name",
    "industry": "industry", "market": "market_board",
}

_SUPPORTED_MARKET_BOARDS = ("沪主板", "深主板", "创业板")


def _get_client():
    global _client
    if _client is None:
        _client = IFindClient()
    return _client


def init(token):
    global _client
    _client = IFindClient(access_token=token)
    return _client


def _code_to_ts(code):
    if code[0] in ("0", "3"):
        return f"{code}.SZ"
    return f"{code}.SH"


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


def _normalize_hist_df(df):
    df = df.rename(columns=_IFIND_HIST_RENAME)
    keep = [v for v in _IFIND_HIST_RENAME.values() if v in df.columns]
    df = df[keep]
    if not df.empty:
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        if "pct_change" not in df.columns and "close" in df.columns:
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["pct_change"] = df["close"].pct_change() * 100
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
    return df


def get_stock_hist(symbol, days=120, retries=2):
    end_date = pd.Timestamp.now().strftime("%Y%m%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days * 2)).strftime("%Y%m%d")
    ts_code = _code_to_ts(symbol)
    client = _get_client()

    for attempt in range(retries):
        try:
            df = client.get_history_quotes(ts_code, start_date, end_date)
            if df is None or df.empty:
                return pd.DataFrame()
            df = _normalize_hist_df(df)
            if len(df) >= 10:
                return df.tail(days).reset_index(drop=True)
            return df.tail(days).reset_index(drop=True)
        except Exception as exc:
            if attempt < retries - 1:
                _logger.warning("iFinD 获取 %s 失败，重试 %s/%s: %s", ts_code, attempt + 1, retries, exc)
                time.sleep(0.5 * (attempt + 1))
            else:
                _logger.warning("iFinD 获取 %s 失败: %s", ts_code, exc)
    return pd.DataFrame()


def get_stock_universe(market_board=None, industry=None, supported_only=True):
    client = _get_client()
    try:
        df = client.get_data_pool("block", "all")
        if df is None or df.empty:
            _logger.warning("iFinD data_pool 为空，回退到 basic_data_service")
            return _fallback_universe(market_board, industry, supported_only)

        cols_map = {k: v for k, v in _IFIND_BASIC_RENAME.items() if k in df.columns}
        df = df.rename(columns=cols_map)

        if "name" not in df.columns and "stockName" in df.columns:
            df["name"] = df["stockName"]
        if "code" not in df.columns and "stockCode" in df.columns:
            df["code"] = df["stockCode"]

        df["market_board"] = df["code"].map(_classify_market_board)
        df["industry"] = df.get("industry", "未分类").fillna("未分类")
        df = df[~df["name"].str.contains("ST|\\*ST|退", na=False)]

        keep_cols = ["code", "name", "market_board", "industry"]
        df = df[[c for c in keep_cols if c in df.columns]].reset_index(drop=True)
    except Exception as exc:
        _logger.warning("iFinD 获取股票池异常: %s", exc)
        return _fallback_universe(market_board, industry, supported_only)

    if supported_only:
        df = df[df["market_board"].isin(_SUPPORTED_MARKET_BOARDS)]
    if market_board and market_board not in ("全部板块", "全部市场", "全部"):
        df = df[df["market_board"] == market_board]
    if industry and industry not in ("全部行业", "全部"):
        df = df[df["industry"] == industry]
    return df.reset_index(drop=True)


def _fallback_universe(market_board=None, industry=None, supported_only=True):
    """iFinD 回退方案：用沪深300+中证500成分股拼接股票池"""
    client = _get_client()
    stocks = pd.DataFrame()
    for pool_code in ["沪深300", "中证500"]:
        try:
            df = client.get_data_pool("index", pool_code)
            if df is not None and not df.empty:
                stocks = pd.concat([stocks, df], ignore_index=True)
        except Exception:
            pass

    if stocks.empty:
        return pd.DataFrame(columns=["code", "name", "market_board", "industry"])

    if "stockCode" in stocks.columns:
        stocks["code"] = stocks["stockCode"].apply(_ts_to_code)
    if "stockName" in stocks.columns:
        stocks["name"] = stocks["stockName"]

    stocks["market_board"] = stocks["code"].map(_classify_market_board)
    stocks["industry"] = "未分类"
    stocks = stocks[~stocks["name"].str.contains("ST|\\*ST|退", na=False)]

    keep_cols = ["code", "name", "market_board", "industry"]
    stocks = stocks[[c for c in keep_cols if c in stocks.columns]].reset_index(drop=True)

    if supported_only:
        stocks = stocks[stocks["market_board"].isin(_SUPPORTED_MARKET_BOARDS)]
    if market_board and market_board not in ("全部板块", "全部市场", "全部"):
        stocks = stocks[stocks["market_board"] == market_board]
    if industry and industry not in ("全部行业", "全部"):
        stocks = stocks[stocks["industry"] == industry]
    return stocks.reset_index(drop=True)


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
    return None


def get_broker_recommend(month=None):
    return {}


def _ts_to_code(ts_code):
    return ts_code.split(".")[0]
