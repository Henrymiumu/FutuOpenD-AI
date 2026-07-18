"""Futu OpenD market data client."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

from futu import (
    KLType,
    Market,
    OpenQuoteContext,
    RET_OK,
    SubType,
)

from .config import settings

logger = logging.getLogger(__name__)


class FutuClientError(Exception):
    """Raised when OpenD request fails."""


class FutuClient:
    """Thin wrapper around futu OpenQuoteContext."""

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or settings.futu_host
        self.port = port or settings.futu_port

    @contextmanager
    def quote_ctx(self):
        ctx = OpenQuoteContext(host=self.host, port=self.port)
        try:
            yield ctx
        finally:
            ctx.close()

    def check_connection(self) -> dict[str, Any]:
        """Ping OpenD and return connection status."""
        try:
            with self.quote_ctx() as ctx:
                ret, data = ctx.get_global_state()
                if ret != RET_OK:
                    return {
                        "connected": False,
                        "host": self.host,
                        "port": self.port,
                        "error": str(data),
                    }
                return {
                    "connected": True,
                    "host": self.host,
                    "port": self.port,
                    "state": data if isinstance(data, dict) else {"raw": str(data)},
                }
        except Exception as e:
            logger.exception("OpenD connection failed")
            return {
                "connected": False,
                "host": self.host,
                "port": self.port,
                "error": str(e),
            }

    def get_market_snapshot(self, codes: list[str]) -> list[dict[str, Any]]:
        """Get real-time market snapshot for stock codes.

        Codes example: ['HK.00700', 'US.AAPL', 'SH.600519']
        """
        if not codes:
            raise FutuClientError("codes list is empty")

        with self.quote_ctx() as ctx:
            ret, data = ctx.get_market_snapshot(codes)
            if ret != RET_OK:
                raise FutuClientError(f"get_market_snapshot failed: {data}")

            rows: list[dict[str, Any]] = []
            for _, row in data.iterrows():
                rows.append(self._snapshot_row_to_dict(row))
            return rows

    def get_stock_basicinfo(self, market: str = "HK", stock_type: str = "STOCK") -> list[dict[str, Any]]:
        """List basic stock info for a market (limited sample for UI)."""
        market_map = {
            "HK": Market.HK,
            "US": Market.US,
            "SH": Market.SH,
            "SZ": Market.SZ,
        }
        m = market_map.get(market.upper())
        if m is None:
            raise FutuClientError(f"Unsupported market: {market}")

        with self.quote_ctx() as ctx:
            ret, data = ctx.get_stock_basicinfo(m, stock_type)
            if ret != RET_OK:
                raise FutuClientError(f"get_stock_basicinfo failed: {data}")

            # Cap to keep payload small
            sample = data.head(50)
            rows = []
            for _, row in sample.iterrows():
                rows.append(
                    {
                        "code": row.get("code"),
                        "name": row.get("name"),
                        "lot_size": _safe(row.get("lot_size")),
                        "stock_type": row.get("stock_type"),
                        "stock_id": _safe(row.get("stock_id")),
                    }
                )
            return rows

    def get_cur_kline(
        self,
        code: str,
        num: int = 60,
        ktype: str = "K_DAY",
    ) -> list[dict[str, Any]]:
        """Get recent K-line bars."""
        ktype_map = {
            "K_1M": KLType.K_1M,
            "K_5M": KLType.K_5M,
            "K_15M": KLType.K_15M,
            "K_30M": KLType.K_30M,
            "K_60M": KLType.K_60M,
            "K_DAY": KLType.K_DAY,
            "K_WEEK": KLType.K_WEEK,
            "K_MON": KLType.K_MON,
        }
        kt = ktype_map.get(ktype.upper(), KLType.K_DAY)

        sub_map = {
            KLType.K_1M: SubType.K_1M,
            KLType.K_5M: SubType.K_5M,
            KLType.K_15M: SubType.K_15M,
            KLType.K_30M: SubType.K_30M,
            KLType.K_60M: SubType.K_60M,
            KLType.K_DAY: SubType.K_DAY,
            KLType.K_WEEK: SubType.K_WEEK,
            KLType.K_MON: SubType.K_MON,
        }
        sub_type = sub_map.get(kt, SubType.K_DAY)

        with self.quote_ctx() as ctx:
            # Subscribe first (required by OpenD for kline in many versions)
            ret_sub, err = ctx.subscribe([code], [sub_type], is_first_push=False)
            if ret_sub != RET_OK:
                logger.warning("subscribe warning: %s", err)

            ret, data = ctx.get_cur_kline(code, num, kt)
            if ret != RET_OK:
                raise FutuClientError(f"get_cur_kline failed: {data}")

            rows = []
            for _, row in data.iterrows():
                rows.append(
                    {
                        "time_key": str(row.get("time_key", "")),
                        "open": _safe(row.get("open")),
                        "close": _safe(row.get("close")),
                        "high": _safe(row.get("high")),
                        "low": _safe(row.get("low")),
                        "volume": _safe(row.get("volume")),
                        "turnover": _safe(row.get("turnover")),
                        "pe_ratio": _safe(row.get("pe_ratio")),
                        "turnover_rate": _safe(row.get("turnover_rate")),
                        "change_rate": _safe(row.get("change_rate")),
                    }
                )
            return rows

    def get_plate_list(self, market: str = "HK") -> list[dict[str, Any]]:
        """Get plate (sector) list for a market."""
        from futu import Plate

        market_map = {
            "HK": Market.HK,
            "US": Market.US,
            "SH": Market.SH,
            "SZ": Market.SZ,
        }
        m = market_map.get(market.upper())
        if m is None:
            raise FutuClientError(f"Unsupported market: {market}")

        with self.quote_ctx() as ctx:
            ret, data = ctx.get_plate_list(m, Plate.ALL)
            if ret != RET_OK:
                raise FutuClientError(f"get_plate_list failed: {data}")

            sample = data.head(40)
            rows = []
            for _, row in sample.iterrows():
                rows.append(
                    {
                        "code": row.get("code"),
                        "plate_name": row.get("plate_name"),
                        "plate_id": _safe(row.get("plate_id")),
                    }
                )
            return rows

    @staticmethod
    def _snapshot_row_to_dict(row) -> dict[str, Any]:
        fields = [
            "code",
            "name",
            "update_time",
            "last_price",
            "open_price",
            "high_price",
            "low_price",
            "prev_close_price",
            "volume",
            "turnover",
            "turnover_rate",
            "amplitude",
            "avg_price",
            "bid_price",
            "ask_price",
            "bid_vol",
            "ask_vol",
            "highest52weeks_price",
            "lowest52weeks_price",
            "pe_ratio",
            "pb_ratio",
            "total_market_val",
            "circular_market_val",
            "net_change_val",
            "change_rate",
            "listing_date",
            "lot_size",
            "price_spread",
            "stock_type",
            "suspension",
            "sec_status",
        ]
        out: dict[str, Any] = {}
        for f in fields:
            if f in row.index:
                out[f] = _safe(row.get(f))
        # derived
        try:
            last_p = float(out.get("last_price") or 0)
            prev = float(out.get("prev_close_price") or 0)
            if prev:
                out["change_rate_calc"] = round((last_p - prev) / prev * 100, 4)
                out["change_val_calc"] = round(last_p - prev, 4)
        except (TypeError, ValueError):
            pass
        return out


def _safe(v: Any) -> Any:
    """Convert numpy / pandas scalars to plain Python types."""
    if v is None:
        return None
    try:
        import math

        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
    except Exception:
        pass
    # numpy types
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    return v


futu_client = FutuClient()
