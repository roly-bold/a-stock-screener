import logging
import os
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
    df = _try_all_pool_methods(client)

    if df is None or df.empty:
        return pd.DataFrame(columns=["code", "name", "market_board", "industry"])

    if supported_only:
        df = df[df["market_board"].isin(_SUPPORTED_MARKET_BOARDS)]
    if market_board and market_board not in ("全部板块", "全部市场", "全部"):
        df = df[df["market_board"] == market_board]
    if industry and industry not in ("全部行业", "全部"):
        df = df[df["industry"] == industry]
    return df.reset_index(drop=True)


def _try_all_pool_methods(client):
    """尝试多种方式获取股票池，返回 DataFrame 或 None"""
    # 方法1: data_pool("block", "all")
    try:
        df = client.get_data_pool("block", "all")
        if df is not None and not df.empty:
            return _normalize_pool_df(df)
    except Exception:
        pass

    # 方法2: 问财智能选股 — 沪深主板
    try:
        sh_codes = client.smart_stock_picking("沪深主板A股", "stock")
        sz_codes = client.smart_stock_picking("深市主板A股", "stock")
        cy_codes = client.smart_stock_picking("创业板A股", "stock")
        all_codes = (sh_codes or []) + (sz_codes or []) + (cy_codes or [])
        if all_codes:
            records = []
            for item in all_codes:
                code = item.get("code", "")
                name = item.get("name", "")
                records.append({"code": _ts_to_code(code) if "." in str(code) else str(code), "name": str(name)})
            df = pd.DataFrame(records)
            df = df.drop_duplicates(subset=["code"])
            df["market_board"] = df["code"].map(_classify_market_board)
            df["industry"] = "未分类"
            df = df[~df["name"].str.contains("ST|\\*ST|退", na=False)]
            if not df.empty:
                return df
    except Exception:
        pass

    # 方法3: 沪深300 + 中证500 成分股
    stocks = pd.DataFrame()
    for query in ["沪深300成分股", "中证500成分股"]:
        try:
            result = client.smart_stock_picking(query, "stock")
            if result:
                records = []
                for item in result:
                    code = item.get("code", "")
                    name = item.get("name", "")
                    records.append({"code": _ts_to_code(code) if "." in str(code) else str(code), "name": str(name)})
                part = pd.DataFrame(records)
                stocks = pd.concat([stocks, part], ignore_index=True)
        except Exception:
            pass
    if not stocks.empty:
        stocks = stocks.drop_duplicates(subset=["code"])
        stocks["market_board"] = stocks["code"].map(_classify_market_board)
        stocks["industry"] = "未分类"
        stocks = stocks[~stocks["name"].str.contains("ST|\\*ST|退", na=False)]
        if not stocks.empty:
            return stocks

    # 方法4: 从 stocks.csv 文件读取
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "stocks.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, dtype={"code": str})
            if not df.empty and "code" in df.columns:
                if "name" not in df.columns:
                    df["name"] = df["code"]
                df["market_board"] = df["code"].map(_classify_market_board)
                df["industry"] = df.get("industry", "未分类").fillna("未分类")
                return df
    except Exception:
        pass

    # 方法5: 根据已知代码段自动生成股票池
    _logger.warning("所有 iFinD 接口均失败，使用代码段生成股票池")
    codes = []
    # 只覆盖实际有股票的范围，减少无效请求
    ranges = [
        ("600000", "603999"),  # 沪主板主要区间
        ("000001", "003099"),  # 深主板主要区间
        ("300001", "301599"),  # 创业板主要区间
    ]
    for start, end in ranges:
        for num in range(int(start), int(end) + 1):
            code = str(num).zfill(6)
            mb = _classify_market_board(code)
            if mb in _SUPPORTED_MARKET_BOARDS:
                codes.append(code)
    if codes:
        df = pd.DataFrame({"code": codes, "name": codes, "market_board": "", "industry": "未分类"})
        df["market_board"] = df["code"].map(_classify_market_board)
        return df

    return None


def _normalize_pool_df(df):
    """标准化 data_pool 返回的 DataFrame"""
    if "stockCode" in df.columns:
        df["code"] = df["stockCode"].apply(_ts_to_code)
    elif "code" not in df.columns:
        return pd.DataFrame()
    if "stockName" in df.columns:
        df["name"] = df["stockName"]
    elif "name" not in df.columns:
        return pd.DataFrame()
    df["market_board"] = df["code"].map(_classify_market_board)
    df["industry"] = df.get("industry", "未分类").fillna("未分类")
    df = df[~df["name"].str.contains("ST|\\*ST|退", na=False)]
    keep_cols = ["code", "name", "market_board", "industry"]
    return df[[c for c in keep_cols if c in df.columns]].reset_index(drop=True)


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
