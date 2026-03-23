from __future__ import annotations

import ast
import json
import math
import re
import threading
import time
from datetime import date, datetime
from urllib import parse, request
from typing import Any

from app.core.config import settings
from app.core.exceptions import ExternalDataError


def _sanitize_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value == "---":
            return None
        value = value.replace("%", "")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def _sanitize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class FundDataService:
    FUND_NAME_JS_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
    FUND_ESTIMATION_URL = "https://fundgz.1234567.com.cn/js/{fund_code}.js"
    FUND_HISTORY_URL = "https://api.fund.eastmoney.com/f10/lsjz"

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def _run_with_timeout(self, loader: Any, error_message: str) -> Any:
        try:
            return loader()
        except TimeoutError as exc:
            raise ExternalDataError(
                f"{error_message}: 外部数据源响应超时，已超过 {settings.fund_data_timeout_seconds:.0f} 秒"
            ) from exc
        except ExternalDataError:
            raise
        except Exception as exc:
            if "timed out" in str(exc).lower():
                raise ExternalDataError(
                    f"{error_message}: 外部数据源响应超时，已超过 {settings.fund_data_timeout_seconds:.0f} 秒"
                ) from exc
            raise ExternalDataError(f"{error_message}: {exc}") from exc

    def _get_or_load(self, key: str, loader: Any, refresh: bool = False) -> Any:
        with self._lock:
            if not refresh and key in self._cache:
                expires_at, value = self._cache[key]
                if expires_at > time.time():
                    return value

        value = loader()
        with self._lock:
            self._cache[key] = (time.time() + settings.cache_ttl_seconds, value)
        return value

    def _http_get(self, url: str, params: dict[str, Any] | None = None, referer: str | None = None) -> str:
        query = f"?{parse.urlencode(params)}" if params else ""
        req = request.Request(
            url=f"{url}{query}",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": referer or "https://fund.eastmoney.com/",
            },
        )
        with request.urlopen(req, timeout=settings.fund_data_timeout_seconds) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def _parse_jsonp(self, content: str) -> dict[str, Any]:
        matched = re.search(r"\((\{.*\})\)", content, re.S)
        if not matched:
            raise ExternalDataError("天天基金返回了无法解析的估算数据")
        try:
            return json.loads(matched.group(1))
        except json.JSONDecodeError as exc:
            raise ExternalDataError("天天基金估算数据格式异常") from exc

    def _load_fund_names(self) -> dict[str, dict[str, str | None]]:
        content = self._run_with_timeout(
            lambda: self._http_get(self.FUND_NAME_JS_URL),
            "获取基金基础信息失败",
        )

        matched = re.search(r"=\s*(\[.*\]);?", content, re.S)
        if not matched:
            raise ExternalDataError("天天基金基金列表返回格式异常")

        try:
            rows = ast.literal_eval(matched.group(1))
        except (SyntaxError, ValueError) as exc:
            raise ExternalDataError("天天基金基金列表解析失败") from exc

        result: dict[str, dict[str, str | None]] = {}
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 4:
                continue
            code = _sanitize_text(row[0])
            if not code:
                continue
            result[code] = {
                "fund_name": _sanitize_text(row[2]),
                "fund_type": _sanitize_text(row[3]),
            }
        return result

    def _load_estimate(self, fund_code: str) -> dict[str, Any]:
        content = self._run_with_timeout(
            lambda: self._http_get(
                self.FUND_ESTIMATION_URL.format(fund_code=fund_code),
                params={"rt": int(time.time() * 1000)},
                referer=f"https://fund.eastmoney.com/{fund_code}.html",
            ),
            f"获取基金 {fund_code} 估算失败",
        )
        payload = self._parse_jsonp(content)
        return {
            "fund_code": fund_code,
            "fund_name": _sanitize_text(payload.get("name")),
            "estimated_nav": _sanitize_value(payload.get("gsz")),
            "unit_nav": _sanitize_value(payload.get("dwjz")),
            "estimate_change_rate": _sanitize_value(payload.get("gszzl")),
            "published_change_rate": None,
            "nav_date": _sanitize_text(payload.get("jzrq")),
            "source": "tiantian-fund-estimation",
        }

    def _load_fund_history_rows(self, fund_code: str, page_size: int = 120) -> list[dict[str, Any]]:
        content = self._run_with_timeout(
            lambda: self._http_get(
                self.FUND_HISTORY_URL,
                params={
                    "fundCode": fund_code,
                    "pageIndex": 1,
                    "pageSize": page_size,
                },
                referer="https://fundf10.eastmoney.com/",
            ),
            f"获取基金 {fund_code} 历史净值失败",
        )

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ExternalDataError(f"基金 {fund_code} 历史净值数据格式异常") from exc

        data = payload.get("Data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return []
        rows = data.get("LSJZList")
        return rows if isinstance(rows, list) else []

    def _load_fund_history(self, fund_code: str) -> dict[str, Any]:
        rows = self._load_fund_history_rows(fund_code=fund_code, page_size=120)
        if not rows:
            raise ExternalDataError(f"基金 {fund_code} 缺少历史净值数据")

        points: list[dict[str, Any]] = []
        for row in rows:
            nav_date_raw = _sanitize_text(row.get("FSRQ"))
            nav_date = nav_date_raw.split(" ")[0] if nav_date_raw else None
            unit_nav = _sanitize_value(row.get("DWJZ"))
            if not nav_date or unit_nav is None:
                continue
            points.append(
                {
                    "nav_date": nav_date,
                    "unit_nav": unit_nav,
                    "change_rate": _sanitize_value(row.get("JZZZL")),
                }
            )

        fund_info = self.get_fund_info(fund_code)
        return {
            "fund_code": fund_code,
            "fund_name": fund_info.get("fund_name") or fund_code,
            "source": "tiantian-fund-history",
            "points": points,
        }

    def get_fund_info(self, fund_code: str, refresh: bool = False) -> dict[str, Any]:
        estimate_info = self._get_or_load(
            f"fund_estimate:{fund_code}",
            lambda: self._load_estimate(fund_code),
            refresh=refresh,
        )

        name_info: dict[str, Any] = {}
        try:
            names = self._get_or_load("fund_names", self._load_fund_names, refresh=refresh)
            name_info = names.get(fund_code, {})
        except Exception:
            name_info = {}

        if not estimate_info and not name_info:
            raise ExternalDataError(f"未找到基金 {fund_code} 的有效数据")

        fund_name = estimate_info.get("fund_name") or name_info.get("fund_name")
        fund_type = name_info.get("fund_type")
        estimated_nav = estimate_info.get("estimated_nav")
        unit_nav = estimate_info.get("unit_nav")
        change_rate = estimate_info.get("estimate_change_rate")
        if change_rate is None:
            change_rate = estimate_info.get("published_change_rate")

        if not fund_name and unit_nav is None and estimated_nav is None:
            raise ExternalDataError(f"未找到基金 {fund_code} 的有效数据")

        source = estimate_info.get("source", "tiantian-fund")
        nav_date = estimate_info.get("nav_date") or datetime.now().date().isoformat()

        if nav_date == date.today().isoformat():
            published_metrics = self.find_history_metrics_by_date(
                fund_code=fund_code,
                target_date=date.today(),
                refresh=refresh,
            )
            if published_metrics:
                published_unit_nav = published_metrics.get("unit_nav")
                published_change_rate = published_metrics.get("change_rate")
                if published_unit_nav is not None:
                    unit_nav = published_unit_nav
                if published_change_rate is not None:
                    change_rate = published_change_rate
                # Today's official NAV is available, so downstream should treat this as final data.
                estimated_nav = None
                source = "tiantian-fund-published"

        return {
            "fund_code": fund_code,
            "fund_name": fund_name or fund_code,
            "fund_type": fund_type,
            "estimated_nav": estimated_nav,
            "unit_nav": unit_nav,
            "change_rate": change_rate,
            "nav_date": nav_date,
            "source": source,
        }

    def get_fund_history(self, fund_code: str, refresh: bool = False) -> dict[str, Any]:
        return self._get_or_load(
            f"fund_history:{fund_code}",
            lambda: self._load_fund_history(fund_code),
            refresh=refresh,
        )

    def get_unit_nav_by_date(self, fund_code: str, target_date: date, refresh: bool = False) -> float:
        rows = self._get_or_load(
            f"fund_history_rows:{fund_code}:1000",
            lambda: self._load_fund_history_rows(fund_code=fund_code, page_size=1000),
            refresh=refresh,
        )

        target = target_date.isoformat()
        for row in rows:
            nav_date_raw = _sanitize_text(row.get("FSRQ"))
            nav_date = nav_date_raw.split(" ")[0] if nav_date_raw else None
            if nav_date != target:
                continue
            unit_nav = _sanitize_value(row.get("DWJZ"))
            if unit_nav is None:
                break
            return unit_nav

        raise ExternalDataError(
            f"基金 {fund_code} 在 {target} 的单位净值尚未公布或当天非交易日，"
            "通常需要在下一个交易日确认份额"
        )

    def find_unit_nav_by_date(self, fund_code: str, target_date: date, refresh: bool = False) -> float | None:
        rows = self._get_or_load(
            f"fund_history_rows:{fund_code}:1000",
            lambda: self._load_fund_history_rows(fund_code=fund_code, page_size=1000),
            refresh=refresh,
        )

        target = target_date.isoformat()
        for row in rows:
            nav_date_raw = _sanitize_text(row.get("FSRQ"))
            nav_date = nav_date_raw.split(" ")[0] if nav_date_raw else None
            if nav_date != target:
                continue
            return _sanitize_value(row.get("DWJZ"))
        return None

    def find_history_metrics_by_date(
        self,
        fund_code: str,
        target_date: date,
        refresh: bool = False,
    ) -> dict[str, float | None] | None:
        rows = self._get_or_load(
            f"fund_history_rows:{fund_code}:1000",
            lambda: self._load_fund_history_rows(fund_code=fund_code, page_size=1000),
            refresh=refresh,
        )

        target = target_date.isoformat()
        for row in rows:
            nav_date_raw = _sanitize_text(row.get("FSRQ"))
            nav_date = nav_date_raw.split(" ")[0] if nav_date_raw else None
            if nav_date != target:
                continue
            return {
                "unit_nav": _sanitize_value(row.get("DWJZ")),
                "change_rate": _sanitize_value(row.get("JZZZL")),
            }
        return None
