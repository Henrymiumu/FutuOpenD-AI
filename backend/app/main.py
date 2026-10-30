"""FastAPI application: Futu OpenD market data + multi-LLM analysis."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import ai_providers
from .config import settings
from .futu_client import FutuClient, FutuClientError, futu_client
from .schemas import (
    AIConfig,
    AnalyzeRequest,
    KlineRequest,
    OpenDConfigRequest,
    SnapshotRequest,
    TestAIRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("futu-ai")

app = FastAPI(
    title="Futu Market AI",
    description="透過 Futu OpenD 取得市場資訊，並以本地/雲端 LLM 進行分析",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    # GitHub Pages is HTTPS; the UI calls this API on localhost. No cookies are used.
    allow_origins=settings.cors_origins + ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Runtime OpenD endpoint (can be updated from UI)
_runtime_client = FutuClient(settings.futu_host, settings.futu_port)


def get_client() -> FutuClient:
    return _runtime_client


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "futu-market-ai"}


@app.get("/api/opend/status")
def opend_status():
    return get_client().check_connection()


@app.post("/api/opend/config")
def opend_config(body: OpenDConfigRequest):
    global _runtime_client
    _runtime_client = FutuClient(body.host, body.port)
    return _runtime_client.check_connection()


@app.post("/api/market/snapshot")
def market_snapshot(body: SnapshotRequest):
    try:
        rows = get_client().get_market_snapshot(body.codes)
        return {"count": len(rows), "data": rows}
    except FutuClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.exception("snapshot failed")
        raise HTTPException(status_code=500, detail=f"OpenD error: {e}") from e


@app.get("/api/market/snapshot")
def market_snapshot_get(codes: str = Query(..., description="Comma-separated codes")):
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list:
        raise HTTPException(status_code=400, detail="codes required")
    return market_snapshot(SnapshotRequest(codes=code_list))


@app.post("/api/market/kline")
def market_kline(body: KlineRequest):
    try:
        rows = get_client().get_cur_kline(body.code, body.num, body.ktype)
        return {"code": body.code, "ktype": body.ktype, "count": len(rows), "data": rows}
    except FutuClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.exception("kline failed")
        raise HTTPException(status_code=500, detail=f"OpenD error: {e}") from e


@app.get("/api/market/basicinfo")
def market_basicinfo(market: str = "HK"):
    try:
        rows = get_client().get_stock_basicinfo(market)
        return {"market": market, "count": len(rows), "data": rows}
    except FutuClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/market/plates")
def market_plates(market: str = "HK"):
    try:
        rows = get_client().get_plate_list(market)
        return {"market": market, "count": len(rows), "data": rows}
    except FutuClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/ai/providers")
def ai_providers_list():
    return {"providers": ai_providers.list_providers()}


@app.post("/api/ai/test")
async def ai_test(body: TestAIRequest):
    cfg = body.ai
    result = await ai_providers.test_provider(
        cfg.provider,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or "AI test failed")
    return result


@app.post("/api/ai/analyze")
async def ai_analyze(body: AnalyzeRequest):
    """Fetch market data (optional) and run LLM analysis."""
    market_payload: dict[str, Any]

    if body.market_data is not None:
        market_payload = {"provided": body.market_data}
    else:
        if not body.codes:
            raise HTTPException(status_code=400, detail="codes or market_data required")
        try:
            snapshots = get_client().get_market_snapshot(body.codes)
            market_payload = {"snapshots": snapshots}
            if body.include_kline:
                kcode = body.kline_code or body.codes[0]
                kline = get_client().get_cur_kline(kcode, body.kline_num, body.kline_type)
                market_payload["kline"] = {
                    "code": kcode,
                    "ktype": body.kline_type,
                    "bars": kline,
                }
        except FutuClientError as e:
            raise HTTPException(status_code=502, detail=f"OpenD: {e}") from e
        except Exception as e:
            logger.exception("market fetch for analyze failed")
            raise HTTPException(status_code=500, detail=f"OpenD error: {e}") from e

    messages = ai_providers.build_market_analysis_prompt(
        market_payload,
        user_question=body.question,
        language=body.language,
    )

    cfg = body.ai
    try:
        result = await ai_providers.chat_completion(
            cfg.provider,
            messages,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    except ai_providers.AIProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.exception("AI analyze failed")
        raise HTTPException(status_code=500, detail=f"AI error: {e}") from e

    return {
        "analysis": result["content"],
        "ai": {
            "provider": result["provider"],
            "model": result["model"],
            "base_url": result["base_url"],
        },
        "market": market_payload,
    }


@app.get("/")
def root():
    return {
        "name": "Futu Market AI API",
        "docs": "/docs",
        "health": "/api/health",
    }
