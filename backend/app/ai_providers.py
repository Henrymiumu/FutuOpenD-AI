"""Multi-provider LLM client: Ollama (local) + OpenAI-compatible APIs."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# Built-in provider templates (user can override base_url / model / api_key)
PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "ollama": {
        "name": "Ollama (本地)",
        "base_url": "http://127.0.0.1:11434",
        "model": "llama3.1:8b",
        "api_style": "ollama",
        "requires_api_key": False,
        "description": "本地 Ollama，預設模型 llama3.1:8b",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_style": "openai",
        "requires_api_key": True,
        "description": "OpenAI 官方 API",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_style": "openai",
        "requires_api_key": True,
        "description": "DeepSeek OpenAI 相容 API",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-5-sonnet-20241022",
        "api_style": "anthropic",
        "requires_api_key": True,
        "description": "Anthropic Claude Messages API",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-3.5-flash",
        "api_style": "gemini",
        "requires_api_key": True,
        "description": "Google Gemini generateContent API",
    },
    "custom": {
        "name": "自訂 OpenAI 相容",
        "base_url": "http://127.0.0.1:8001/v1",
        "model": "custom-model",
        "api_style": "openai",
        "requires_api_key": False,
        "description": "任何 OpenAI Chat Completions 相容端點（LM Studio、vLLM、Together 等）",
    },
}


class AIProviderError(Exception):
    """LLM call failed."""


def list_providers() -> list[dict[str, Any]]:
    return [
        {"id": pid, **{k: v for k, v in meta.items()}}
        for pid, meta in PROVIDER_PRESETS.items()
    ]


def build_market_analysis_prompt(
    market_data: dict[str, Any] | list[Any],
    user_question: str | None = None,
    language: str = "zh-TW",
) -> list[dict[str, str]]:
    """Build chat messages for market analysis."""
    system = (
        "你是一位專業的金融市場分析師。請根據提供的即時/近期市場數據進行客觀分析。\n"
        "要求：\n"
        "1. 先總結關鍵價格與成交數據\n"
        "2. 分析短線技術面（趨勢、波動、量價）\n"
        "3. 列出可能的機會與風險（非投資建議）\n"
        "4. 給出觀察重點，語氣專業、簡潔\n"
        "5. 明確聲明：分析僅供參考，不構成投資建議\n"
        f"請使用語言：{language}"
    )
    data_json = json.dumps(market_data, ensure_ascii=False, indent=2, default=str)
    user = f"以下是市場數據（JSON）：\n```json\n{data_json}\n```\n"
    if user_question and user_question.strip():
        user += f"\n使用者問題：{user_question.strip()}\n"
    else:
        user += "\n請對以上數據做綜合分析。\n"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def chat_completion(
    provider: str,
    messages: list[dict[str, str]],
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Call the selected LLM provider and return text result."""
    preset = PROVIDER_PRESETS.get(provider)
    if not preset:
        raise AIProviderError(f"Unknown provider: {provider}")

    style = preset["api_style"]
    base = (base_url or preset["base_url"]).rstrip("/")
    mdl = model or preset["model"]
    key = (api_key or "").strip()

    if preset["requires_api_key"] and not key and provider != "custom":
        raise AIProviderError(f"Provider '{provider}' requires an API key")

    if style == "ollama":
        content = await _ollama_chat(base, mdl, messages, temperature, timeout)
    elif style == "openai":
        content = await _openai_chat(base, mdl, key, messages, temperature, max_tokens, timeout)
    elif style == "anthropic":
        content = await _anthropic_chat(base, mdl, key, messages, temperature, max_tokens, timeout)
    elif style == "gemini":
        content = await _gemini_chat(base, mdl, key, messages, temperature, max_tokens, timeout)
    else:
        raise AIProviderError(f"Unsupported api_style: {style}")

    return {
        "provider": provider,
        "model": mdl,
        "base_url": base,
        "content": content,
    }


async def _ollama_chat(
    base: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    timeout: float,
) -> str:
    url = f"{base}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.ConnectError as e:
            raise AIProviderError(
                f"無法連線 Ollama ({base})。請確認已啟動 ollama serve，並已拉取模型：ollama pull {model}"
            ) from e
        if resp.status_code >= 400:
            raise AIProviderError(f"Ollama error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return data.get("message", {}).get("content") or data.get("response") or ""


async def _openai_chat(
    base: str,
    model: str,
    api_key: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    url = f"{base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as e:
            raise AIProviderError(f"無法連線 LLM API ({base}): {e}") from e
        if resp.status_code >= 400:
            raise AIProviderError(f"OpenAI-compatible API error {resp.status_code}: {resp.text[:800]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AIProviderError(f"Unexpected response shape: {data}") from e


async def _anthropic_chat(
    base: str,
    model: str,
    api_key: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    system = ""
    chat_msgs = []
    for m in messages:
        if m["role"] == "system":
            system = (system + "\n" + m["content"]).strip() if system else m["content"]
        else:
            chat_msgs.append({"role": m["role"], "content": m["content"]})

    url = f"{base}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": chat_msgs,
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as e:
            raise AIProviderError(f"無法連線 Anthropic ({base}): {e}") from e
        if resp.status_code >= 400:
            raise AIProviderError(f"Anthropic error {resp.status_code}: {resp.text[:800]}")
        data = resp.json()
        parts = data.get("content") or []
        texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "\n".join(texts)


async def _gemini_chat(
    base: str,
    model: str,
    api_key: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    # Convert messages to Gemini format
    system_parts = []
    contents = []
    for m in messages:
        if m["role"] == "system":
            system_parts.append(m["content"])
        elif m["role"] == "user":
            contents.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] == "assistant":
            contents.append({"role": "model", "parts": [{"text": m["content"]}]})

    url = f"{base}/models/{model}:generateContent"
    params = {"key": api_key}
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, params=params, json=payload)
        except httpx.ConnectError as e:
            raise AIProviderError(f"無法連線 Gemini: {e}") from e
        if resp.status_code >= 400:
            raise AIProviderError(f"Gemini error {resp.status_code}: {resp.text[:800]}")
        data = resp.json()
        try:
            candidate = data["candidates"][0]
            parts = candidate.get("content", {}).get("parts") or []
            texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
            if texts:
                return "\n".join(texts)
            reason = candidate.get("finishReason", "UNKNOWN")
            thoughts = (data.get("usageMetadata") or {}).get("thoughtsTokenCount", 0)
            raise AIProviderError(
                f"Gemini returned empty text (finishReason={reason}, "
                f"thoughtsTokenCount={thoughts}, maxOutputTokens={max_tokens}). "
                "Newer Gemini models spend tokens on thinking; raise Max Tokens "
                "(e.g. 1024+) or use a non-thinking model."
            )
        except AIProviderError:
            raise
        except (KeyError, IndexError, TypeError) as e:
            raise AIProviderError(f"Unexpected Gemini response: {data}") from e


async def test_provider(
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Lightweight connectivity test."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Reply briefly."},
        {"role": "user", "content": "Reply with exactly: OK"},
    ]
    # Gemini 2.5/3.x thinking models spend output budget on thoughts first;
    # 32 is too low and yields empty content with finishReason=MAX_TOKENS.
    test_max_tokens = 512 if provider == "gemini" else 64
    try:
        result = await chat_completion(
            provider,
            messages,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=test_max_tokens,
            temperature=0,
            timeout=30.0,
        )
        return {"ok": True, **result}
    except AIProviderError as e:
        return {"ok": False, "provider": provider, "error": str(e)}
