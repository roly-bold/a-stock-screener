import os
import time
import logging
import requests
import pandas as pd

BASE_URL = "https://quantapi.51ifind.com/api/v1"
_logger = logging.getLogger(__name__)
_DEFAULT_TIMEOUT = float(os.environ.get("IFIND_TIMEOUT_SECONDS", "12"))
_DEFAULT_RETRIES = int(os.environ.get("IFIND_RETRIES", "2"))


def _to_date_str(d):
    """Convert YYYYMMDD string to YYYY-MM-DD for iFinD API."""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


class IFindClient:
    def __init__(self, access_token=None, timeout=_DEFAULT_TIMEOUT):
        self._token = access_token or os.environ.get("IFIND_ACCESS_TOKEN", "")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "access_token": self._token,
        })

    def _post(self, endpoint, body, retries=_DEFAULT_RETRIES):
        url = f"{BASE_URL}/{endpoint}"
        for attempt in range(retries):
            try:
                resp = self._session.post(url, json=body, timeout=self._timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    errcode = data.get("errcode", data.get("errorcode", data.get("code", -1)))
                    if errcode == 0:
                        return data.get("data", data)
                    errmsg = data.get("errmsg", data.get("message", str(data)))
                    _logger.warning("iFinD API error (errcode=%s): %s", errcode, errmsg)
                    return None
                elif resp.status_code == 401:
                    _logger.error("iFinD access_token 无效或已过期")
                    return None
                elif resp.status_code == 429:
                    wait = min(2 ** attempt, 30)
                    _logger.warning("iFinD 限流，等待 %ss 重试", wait)
                    time.sleep(wait)
                else:
                    _logger.warning("iFinD HTTP %s: %s", resp.status_code, resp.text[:200])
            except requests.Timeout:
                if attempt < retries - 1:
                    time.sleep(0.5 * (attempt + 1))
            except Exception as exc:
                if attempt < retries - 1:
                    _logger.warning("iFinD 请求失败，重试 %s/%s: %s", attempt + 1, retries, exc)
                    time.sleep(0.5 * (attempt + 1))
                else:
                    _logger.error("iFinD 请求失败，已放弃: %s", exc)
        return None

    def get_history_quotes(self, code, start_date, end_date, indicators="open,high,low,close,volume,amount,pctChange"):
        sd = _to_date_str(start_date)
        ed = _to_date_str(end_date)
        body = {
            "codes": code,
            "indicators": indicators,
            "startdate": sd,
            "enddate": ed,
            "functionpara": {"Fill": "Blank"},
        }
        result = self._post("cmd_history_quotation", body)
        if not result or "tables" not in result:
            return pd.DataFrame()
        try:
            tables = result["tables"]
            if not tables:
                return pd.DataFrame()
            records = []
            for row in tables[0].get("rows", tables[0].get("data", [])):
                records.append(row)
            if not records:
                return pd.DataFrame()
            df = pd.DataFrame(records)
            return df
        except Exception as exc:
            _logger.warning("iFinD history_quotes 解析失败: %s", exc)
            return pd.DataFrame()

    def get_basic_info(self, codes):
        body = {
            "codes": ",".join(codes) if isinstance(codes, list) else codes,
            "indicators": "stockCode,stockName,industry,market",
        }
        result = self._post("basic_data_service", body)
        if not result:
            return pd.DataFrame()
        try:
            tables = result.get("tables", [])
            if not tables:
                return pd.DataFrame()
            records = []
            for row in tables[0].get("rows", tables[0].get("data", [])):
                records.append(row)
            return pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as exc:
            _logger.warning("iFinD basic_data_service 解析失败: %s", exc)
            return pd.DataFrame()

    def get_real_time_quotes(self, codes):
        body = {
            "codes": ",".join(codes) if isinstance(codes, list) else codes,
            "indicators": "latest,open,high,low,volume,amount,pctChange",
        }
        result = self._post("real_time_quotation", body)
        if not result:
            return {}
        try:
            tables = result.get("tables", [])
            if not tables:
                return {}
            quotes = {}
            for row in tables[0].get("rows", tables[0].get("data", [])):
                code = row.get("stockCode", row.get("code", ""))
                quotes[code] = row
            return quotes
        except Exception as exc:
            _logger.warning("iFinD real_time_quotation 解析失败: %s", exc)
            return {}

    def smart_stock_picking(self, query, search_type="stock"):
        body = {
            "searchstring": query,
            "searchtype": search_type,
        }
        result = self._post("smart_stock_picking", body)
        if not result:
            return []
        try:
            tables = result.get("tables", [])
            if not tables:
                return []
            codes = []
            for row in tables[0].get("rows", tables[0].get("data", [])):
                code = row.get("stockCode", row.get("code", ""))
                name = row.get("stockName", row.get("name", ""))
                codes.append({"code": code, "name": name})
            return codes
        except Exception as exc:
            _logger.warning("iFinD smart_stock_picking 解析失败: %s", exc)
            return []

    def get_data_pool(self, pool_type, pool_code):
        body = {
            "poolType": pool_type,
            "poolCode": pool_code,
        }
        result = self._post("data_pool", body)
        if not result:
            return pd.DataFrame()
        try:
            tables = result.get("tables", [])
            if not tables:
                return pd.DataFrame()
            records = []
            for row in tables[0].get("rows", tables[0].get("data", [])):
                records.append(row)
            return pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as exc:
            _logger.warning("iFinD data_pool 解析失败: %s", exc)
            return pd.DataFrame()

    def get_date_sequence(self, codes, indicators, start_date, end_date):
        sd = _to_date_str(start_date)
        ed = _to_date_str(end_date)
        body = {
            "codes": ",".join(codes) if isinstance(codes, list) else codes,
            "indicators": indicators,
            "startdate": sd,
            "enddate": ed,
            "functionpara": {"Fill": "Blank"},
        }
        result = self._post("date_sequence", body)
        if not result:
            return pd.DataFrame()
        try:
            tables = result.get("tables", [])
            if not tables:
                return pd.DataFrame()
            records = []
            for row in tables[0].get("rows", tables[0].get("data", [])):
                records.append(row)
            return pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as exc:
            _logger.warning("iFinD date_sequence 解析失败: %s", exc)
            return pd.DataFrame()
