from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import math
import re
import threading
import time
from datetime import datetime
from typing import Any

import akshare as ak
import pandas as pd

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
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def _run_with_timeout(self, loader: Any, error_message: str) -> Any:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(loader)
        try:
            return future.result(timeout=settings.akshare_timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise ExternalDataError(
                f"{error_message}: 外部数据源响应超时，已超过 {settings.akshare_timeout_seconds:.0f} 秒"
            ) from exc
        except ExternalDataError:
            raise
        except Exception as exc:
            raise ExternalDataError(f"{error_message}: {exc}") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

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

    def _load_fund_names(self) -> dict[str, dict[str, str | None]]:
        data = self._run_with_timeout(ak.fund_name_em, "获取基金基础信息失败")

        result: dict[str, dict[str, str | None]] = {}
        for _, row in data.iterrows():
            code = _sanitize_text(row.get("基金代码"))
            if not code:
                continue
            result[code] = {
                "fund_name": _sanitize_text(row.get("基金简称")),
                "fund_type": _sanitize_text(row.get("基金类型")),
            }
        return result

    def _load_estimates(self) -> dict[str, dict[str, Any]]:
        data = self._run_with_timeout(
            lambda: ak.fund_value_estimation_em(symbol="全部"),
            "获取基金估算失败",
        )

        estimate_col = next((col for col in data.columns if "估算值" in str(col)), None)
        published_nav_col = next((col for col in data.columns if "公布数据-单位净值" in str(col)), None)
        nav_date_col = next((col for col in data.columns if str(col).endswith("-单位净值") and "交易日-公布数据" not in str(col)), None)
        estimate_rate_col = next((col for col in data.columns if "估算增长率" in str(col)), None)
        published_rate_col = next((col for col in data.columns if "公布数据-日增长率" in str(col)), None)

        result: dict[str, dict[str, Any]] = {}
        for _, row in data.iterrows():
            code = _sanitize_text(row.get("基金代码"))
            if not code:
                continue
            nav_date = None
            if nav_date_col:
                matched = re.match(r"(\d{4}-\d{2}-\d{2})-单位净值", str(nav_date_col))
                nav_date = matched.group(1) if matched else None
            result[code] = {
                "fund_code": code,
                "fund_name": _sanitize_text(row.get("基金名称")),
                "estimated_nav": _sanitize_value(row.get(estimate_col)) if estimate_col else None,
                "unit_nav": _sanitize_value(row.get(published_nav_col)) if published_nav_col else None,
                "estimate_change_rate": _sanitize_value(row.get(estimate_rate_col)) if estimate_rate_col else None,
                "published_change_rate": _sanitize_value(row.get(published_rate_col)) if published_rate_col else None,
                "nav_date": nav_date,
                "source": "akshare-estimation",
            }
        return result

    def _load_open_fund_daily(self) -> dict[str, dict[str, Any]]:
        data = self._run_with_timeout(ak.fund_open_fund_daily_em, "获取开放式基金净值失败")

        unit_nav_col = next((col for col in data.columns if col == "单位净值"), None)
        if not unit_nav_col:
            unit_nav_col = next((col for col in data.columns if str(col).endswith("-单位净值") and "前交易日" not in str(col)), None)
        prev_unit_nav_col = next((col for col in data.columns if "前交易日" in str(col) and "单位净值" in str(col)), None)
        change_rate_col = next((col for col in data.columns if "日增长率" in str(col)), None)
        nav_date = None
        if unit_nav_col:
            matched = re.match(r"(\d{4}-\d{2}-\d{2})-单位净值", str(unit_nav_col))
            nav_date = matched.group(1) if matched else datetime.now().date().isoformat()

        result: dict[str, dict[str, Any]] = {}
        for _, row in data.iterrows():
            code = _sanitize_text(row.get("基金代码"))
            if not code:
                continue
            result[code] = {
                "fund_code": code,
                "fund_name": _sanitize_text(row.get("基金简称")),
                "unit_nav": _sanitize_value(row.get(unit_nav_col)) if unit_nav_col else None,
                "prev_unit_nav": _sanitize_value(row.get(prev_unit_nav_col)) if prev_unit_nav_col else None,
                "change_rate": _sanitize_value(row.get(change_rate_col)) if change_rate_col else None,
                "nav_date": nav_date,
                "source": "akshare-open-fund-daily",
            }
        return result

    def _load_overview(self, fund_code: str) -> dict[str, Any]:
        try:
            data = self._run_with_timeout(
                lambda: ak.fund_overview_em(symbol=fund_code),
                f"获取基金 {fund_code} 概览失败",
            )
        except Exception:
            return {}
        if isinstance(data, pd.DataFrame) and not data.empty:
            row = data.iloc[0]
            return {
                "fund_name": _sanitize_text(row.get("基金简称")),
                "fund_type": _sanitize_text(row.get("基金类型")),
            }
        return {}

    def _load_fund_history(self, fund_code: str) -> dict[str, Any]:
        data = self._run_with_timeout(
            lambda: ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势"),
            f"获取基金 {fund_code} 历史净值失败",
        )

        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ExternalDataError(f"基金 {fund_code} 缺少历史净值数据")

        points: list[dict[str, Any]] = []
        for _, row in data.tail(120).iterrows():
            nav_date = _sanitize_text(row.get("净值日期"))
            unit_nav = _sanitize_value(row.get("单位净值"))
            if not nav_date or unit_nav is None:
                continue
            points.append(
                {
                    "nav_date": nav_date,
                    "unit_nav": unit_nav,
                    "change_rate": _sanitize_value(row.get("日增长率")),
                }
            )

        fund_info = self.get_fund_info(fund_code)
        return {
            "fund_code": fund_code,
            "fund_name": fund_info.get("fund_name") or fund_code,
            "source": "akshare-open-fund-history",
            "points": points,
        }

    def get_fund_info(self, fund_code: str, refresh: bool = False) -> dict[str, Any]:
        names = self._get_or_load("fund_names", self._load_fund_names, refresh=refresh)
        estimates = self._get_or_load("fund_estimates", self._load_estimates, refresh=refresh)
        daily = self._get_or_load("fund_open_daily", self._load_open_fund_daily, refresh=refresh)

        name_info = names.get(fund_code, {})
        estimate_info = estimates.get(fund_code, {})
        daily_info = daily.get(fund_code, {})
        overview = self._load_overview(fund_code) if not name_info.get("fund_name") else {}

        fund_name = estimate_info.get("fund_name") or daily_info.get("fund_name") or name_info.get("fund_name") or overview.get("fund_name")
        fund_type = name_info.get("fund_type") or overview.get("fund_type")
        estimated_nav = estimate_info.get("estimated_nav")
        unit_nav = estimate_info.get("unit_nav") or daily_info.get("unit_nav")
        change_rate = estimate_info.get("estimate_change_rate")
        if change_rate is None:
            change_rate = estimate_info.get("published_change_rate") or daily_info.get("change_rate")

        if not fund_name and unit_nav is None and estimated_nav is None:
            raise ExternalDataError(f"未找到基金 {fund_code} 的有效数据")

        source = estimate_info.get("source") if estimated_nav is not None else daily_info.get("source", "akshare")
        return {
            "fund_code": fund_code,
            "fund_name": fund_name or fund_code,
            "fund_type": fund_type,
            "estimated_nav": estimated_nav,
            "unit_nav": unit_nav,
            "change_rate": change_rate,
            "nav_date": estimate_info.get("nav_date") or daily_info.get("nav_date"),
            "source": source,
        }

    def get_fund_history(self, fund_code: str, refresh: bool = False) -> dict[str, Any]:
        return self._get_or_load(
            f"fund_history:{fund_code}",
            lambda: self._load_fund_history(fund_code),
            refresh=refresh,
        )
