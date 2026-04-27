import os
import json
import logging
import pandas as pd
from tqdm import tqdm

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_logger = logging.getLogger(__name__)
_SUPPORTED_MARKET_BOARDS = ("沪主板", "深主板", "创业板")

_backend = None
_backend_name = None


def _load_config():
    env_token = os.environ.get("TUSHARE_TOKEN", "")
    env_ifind = os.environ.get("IFIND_ACCESS_TOKEN", "")
    env_source = os.environ.get("DATA_SOURCE", "")
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    if env_token:
        data["tushare_token"] = env_token
    if env_ifind:
        data["ifind_access_token"] = env_ifind
    if env_source:
        data["data_source"] = env_source
    return data


def _get_backend():
    global _backend, _backend_name
    config = _load_config()
    ds = config.get("data_source", "tushare")
    if _backend is not None and _backend_name == ds:
        return _backend

    if ds == "tushare":
        import tushare_backend as backend
        token = config.get("tushare_token", "")
        if not token:
            raise RuntimeError("未配置 tushare token，请运行: python main.py --setup TOKEN")
        backend.init(token)
    elif ds == "ifind":
        import ifind_backend as backend
        token = config.get("ifind_access_token", "")
        if not token:
            raise RuntimeError("未配置 iFinD token，请运行: python main.py --setup-ifind TOKEN")
        backend.init(token)
    else:
        raise ValueError(f"未知数据源: {ds}，可选 tushare / ifind")

    _backend = backend
    _backend_name = ds
    return _backend


def _code_to_ts(code):
    """纯数字代码转 tushare/iFinD 格式: 000001 -> 000001.SZ"""
    if code[0] in ("0", "3"):
        return f"{code}.SZ"
    return f"{code}.SH"


def _ts_to_code(ts_code):
    """tushare/iFinD 格式转纯数字: 000001.SZ -> 000001"""
    return ts_code.split(".")[0]


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


def has_capability(name):
    """查询当前后端是否支持某项能力"""
    if name == "chip_perf":
        return _backend_name == "tushare"
    if name == "broker_recommend":
        return _backend_name == "tushare"
    if name == "realtime_quotes":
        return _backend_name == "ifind"
    if name == "smart_screening":
        return _backend_name == "ifind"
    return False


def get_data_source_name():
    config = _load_config()
    return config.get("data_source", "tushare")


def set_data_source(name):
    global _backend, _backend_name
    config = _load_config()
    config["data_source"] = name
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    _backend = None
    _backend_name = None


# ---- Delegated public API ----

def get_stock_hist(symbol, days=120, retries=None):
    return _get_backend().get_stock_hist(symbol, days=days, retries=retries)


def get_stock_universe(market_board=None, industry=None, supported_only=True):
    return _get_backend().get_stock_universe(market_board, industry, supported_only)


def get_scan_universe_options():
    return _get_backend().get_scan_universe_options()


def get_stock_list():
    return _get_backend().get_stock_list()


def get_chip_perf(ts_code, trade_date=None):
    return _get_backend().get_chip_perf(ts_code, trade_date)


def get_broker_recommend(month=None):
    return _get_backend().get_broker_recommend(month)


def smart_screen(query):
    backend = _get_backend()
    if hasattr(backend, "smart_screen"):
        return backend.smart_screen(query)
    raise RuntimeError("当前数据源不支持问财智能选股")


# ---- Data-source-agnostic utilities (stay in facade) ----

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
        import time
        time.sleep(delay)
    return results
