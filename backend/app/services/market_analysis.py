from __future__ import annotations

import json
import math
import threading
import time
from datetime import datetime
from typing import Any
from urllib import parse, request

from app.core.config import settings
from app.core.exceptions import ExternalDataError
from app.schemas.valuation import PortfolioValuationResponse

INDEX_ORDER = ["000001", "399001", "399006"]
INDEX_NAME_MAP = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
}


class MarketAnalysisService:
    INDEX_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    SECTOR_URL = "https://push2.eastmoney.com/api/qt/clist/get"

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

    def _http_get(self, url: str, params: dict[str, Any], referer: str) -> dict[str, Any]:
        req = request.Request(
            url=f"{url}?{parse.urlencode(params)}",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": referer,
            },
        )
        with request.urlopen(req, timeout=settings.fund_data_timeout_seconds) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ExternalDataError("东方财富返回了无法解析的数据") from exc
        return payload

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(numeric):
            return None
        return numeric

    @staticmethod
    def _to_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _load_market_indexes(self) -> list[dict[str, Any]]:
        payload = self._run_with_timeout(
            lambda: self._http_get(
                self.INDEX_URL,
                params={
                    "fltt": "2",
                    "invt": "2",
                    "fields": "f12,f14,f2,f3,f4,f5,f6",
                    "secids": "1.000001,0.399001,0.399006",
                    "pn": "1",
                    "pz": "20",
                    "po": "1",
                    "np": "1",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                },
                referer="https://quote.eastmoney.com/",
            ),
            "获取大盘指数失败",
        )

        data = payload.get("data") if isinstance(payload, dict) else None
        diff = data.get("diff") if isinstance(data, dict) else None
        if not isinstance(diff, list):
            raise ExternalDataError("东方财富指数数据格式异常")

        rows: list[dict[str, Any]] = []
        for item in diff:
            if not isinstance(item, dict):
                continue
            code = self._to_text(item.get("f12"))
            if not code:
                continue
            rows.append(
                {
                    "code": code,
                    "name": INDEX_NAME_MAP.get(code) or self._to_text(item.get("f14")) or code,
                    "latest": self._to_float(item.get("f2")),
                    "change_rate": self._to_float(item.get("f3")),
                    "change_amount": self._to_float(item.get("f4")),
                    "volume": self._to_float(item.get("f5")),
                    "turnover": self._to_float(item.get("f6")),
                }
            )

        ordered = sorted(rows, key=lambda x: INDEX_ORDER.index(x["code"]) if x["code"] in INDEX_ORDER else 99)
        return ordered

    def _load_sector_rankings(self) -> list[dict[str, Any]]:
        payload = self._run_with_timeout(
            lambda: self._http_get(
                self.SECTOR_URL,
                params={
                    "pn": "1",
                    "pz": "60",
                    "po": "1",
                    "np": "1",
                    "fltt": "2",
                    "invt": "2",
                    "fid": "f3",
                    "fs": "m:90+t:2",
                    "fields": "f12,f14,f3,f62",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                },
                referer="https://quote.eastmoney.com/center/boardlist.html",
            ),
            "获取板块排行失败",
        )

        data = payload.get("data") if isinstance(payload, dict) else None
        diff = data.get("diff") if isinstance(data, dict) else None
        if not isinstance(diff, list):
            raise ExternalDataError("东方财富板块数据格式异常")

        rows: list[dict[str, Any]] = []
        for item in diff:
            if not isinstance(item, dict):
                continue
            name = self._to_text(item.get("f14"))
            if not name:
                continue
            rows.append(
                {
                    "code": self._to_text(item.get("f12")),
                    "name": name,
                    "change_rate": self._to_float(item.get("f3")),
                    "main_net_inflow": self._to_float(item.get("f62")),
                }
            )
        return rows

    def get_market_overview(self, refresh: bool = False, board_limit: int = 5) -> dict[str, Any]:
        limit = max(1, min(board_limit, 20))
        indexes = self._get_or_load("market:indexes", self._load_market_indexes, refresh=refresh)
        sectors = self._get_or_load("market:sectors", self._load_sector_rankings, refresh=refresh)

        index_rates = [item.get("change_rate") for item in indexes if isinstance(item.get("change_rate"), float)]
        up_count = len([r for r in index_rates if r > 0])
        down_count = len([r for r in index_rates if r < 0])
        flat_count = len(index_rates) - up_count - down_count
        avg_change_rate = round(sum(index_rates) / len(index_rates), 4) if index_rates else None

        sorted_sectors = sorted(
            sectors,
            key=lambda x: x.get("change_rate") if isinstance(x.get("change_rate"), float) else -9999,
            reverse=True,
        )
        leaders = sorted_sectors[:limit]
        laggards = sorted(
            sectors,
            key=lambda x: x.get("change_rate") if isinstance(x.get("change_rate"), float) else 9999,
        )[:limit]

        market_breadth_up = len([s for s in sectors if isinstance(s.get("change_rate"), float) and s["change_rate"] > 0])
        market_breadth_down = len([s for s in sectors if isinstance(s.get("change_rate"), float) and s["change_rate"] < 0])

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "eastmoney-push2",
            "indexes": indexes,
            "market_stats": {
                "index_up_count": up_count,
                "index_down_count": down_count,
                "index_flat_count": flat_count,
                "average_index_change_rate": avg_change_rate,
                "sector_up_count": market_breadth_up,
                "sector_down_count": market_breadth_down,
            },
            "sector_rankings": {
                "leaders": leaders,
                "laggards": laggards,
            },
        }

    def build_market_analysis(
        self,
        market_overview: dict[str, Any],
        portfolio: PortfolioValuationResponse,
        max_positions: int = 8,
    ) -> dict[str, Any]:
        position_values: list[dict[str, Any]] = []
        for item in portfolio.items:
            base_value = item.market_value if item.market_value is not None else item.cost_value
            if base_value is None or base_value <= 0:
                continue
            position_values.append(
                {
                    "fund_code": item.fund_code,
                    "fund_name": item.fund_name or item.fund_code,
                    "market_value": round(base_value, 4),
                    "profit_rate": item.profit_rate,
                    "status": item.status,
                }
            )

        total_value = sum(x["market_value"] for x in position_values)
        sorted_positions = sorted(position_values, key=lambda x: x["market_value"], reverse=True)
        distribution = []
        for pos in sorted_positions[: max(1, min(max_positions, 20))]:
            weight = round(pos["market_value"] / total_value, 4) if total_value else 0.0
            distribution.append({**pos, "weight": weight})

        top_weight = distribution[0]["weight"] if distribution else 0.0

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "market_overview": market_overview,
            "portfolio_performance": {
                "total_cost": portfolio.total_cost,
                "total_market_value": portfolio.total_market_value,
                "total_profit": portfolio.total_profit,
                "total_profit_rate": portfolio.total_profit_rate,
                "success_count": portfolio.success_count,
                "failed_count": portfolio.failed_count,
            },
            "position_distribution": {
                "total_positions": len(position_values),
                "max_position_weight": top_weight,
                "items": distribution,
            },
        }
