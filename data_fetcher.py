import os
import time
import json
import tushare as ts
import tushare.pro.client as client
import pandas as pd
from tqdm import tqdm

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_pro = None


def _load_config():
    env_token = os.environ.get("TUSHARE_TOKEN", "")
    env_url = os.environ.get("TUSHARE_API_URL", "")
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    if env_token:
        data["tushare_token"] = env_token
    if env_url:
        data["tushare_api_url"] = env_url
    return data


def _get_pro():
    global _pro
    if _pro is not None:
        return _pro
    config = _load_config()
    token = config.get("tushare_token", "")
    api_url = config.get("tushare_api_url", "http://tushare.xyz")
    if not token:
        raise RuntimeError("未配置 tushare token，请运行: python main.py --setup")
    client.DataApi._DataApi__http_url = api_url
    _pro = ts.pro_api(token)
    return _pro


def _code_to_ts(code):
    """纯数字代码转 tushare 格式: 000001 -> 000001.SZ, 600000 -> 600000.SH"""
    if code[0] in ("0", "3"):
        return f"{code}.SZ"
    return f"{code}.SH"


def _ts_to_code(ts_code):
    """tushare 格式转纯数字: 000001.SZ -> 000001"""
    return ts_code.split(".")[0]


def get_stock_list():
    """获取A股全部股票列表，过滤ST/退市/北交所/科创板"""
    pro = _get_pro()
    df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,area,industry")
    df = df.rename(columns={"symbol": "code"})
    df = df[~df["name"].str.contains("ST|\\*ST|退", na=False)]
    df = df[~df["code"].str.startswith(("688", "8", "4", "9"), na=False)]
    return df[["code", "name"]].reset_index(drop=True)


_TUSHARE_RENAME = {
    "trade_date": "date", "open": "open", "close": "close",
    "high": "high", "low": "low", "vol": "volume",
    "amount": "amount", "pct_chg": "pct_change", "change": "change"
}


def _normalize_hist_df(df, rename_map):
    df = df.rename(columns=rename_map)
    keep = [v for v in rename_map.values() if v in df.columns]
    df = df[keep]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    if "pct_change" not in df.columns and "close" in df.columns:
        df["pct_change"] = df["close"].pct_change() * 100
    if "volume" in df.columns:
        df["volume"] = df["volume"].astype(float)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def get_stock_hist(symbol, days=120, retries=3):
    """获取单只股票日K数据（前复权），tushare 主源"""
    end_date = pd.Timestamp.now().strftime("%Y%m%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days * 2)).strftime("%Y%m%d")
    ts_code = _code_to_ts(symbol)

    for attempt in range(retries):
        try:
            pro = _get_pro()
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

            df = _normalize_hist_df(df, _TUSHARE_RENAME)
            if len(df) >= 10:
                return df.tail(days).reset_index(drop=True)
        except Exception:
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
    return pd.DataFrame()


def load_csv(path, days=120):
    """从CSV文件加载历史数据"""
    df = pd.read_csv(path, parse_dates=["date"])
    required = ["date", "open", "close", "high", "low", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV缺少必要列: {missing}")
    if "pct_change" not in df.columns:
        df["pct_change"] = df["close"].pct_change() * 100
    df = df.dropna(subset=["pct_change"]).reset_index(drop=True)
    return df.tail(days).reset_index(drop=True)


def scan_all_stocks(stock_list, days=120, delay=0.3):
    """扫描全市场，返回 {code: (name, DataFrame)}"""
    results = {}
    total = len(stock_list)
    for _, row in tqdm(stock_list.iterrows(), total=total, desc="扫描股票"):
        code, name = row["code"], row["name"]
        df = get_stock_hist(code, days=days)
        if not df.empty and len(df) >= 30:
            results[code] = (name, df)
        time.sleep(delay)
    return results


def get_chip_perf(ts_code, trade_date=None):
    """获取单只股票筹码成本和胜率"""
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
    """获取券商月度金股，返回 {ts_code: [broker1, broker2, ...]}"""
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
