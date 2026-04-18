"""Model-agnostic LLM client for AI features.

Supports OpenAI, Anthropic (Claude), and Ollama providers via a unified interface.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    """Unified client for multiple LLM providers."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str = "",
        base_url: str = "",
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Send a completion request to the configured provider."""
        return await self._call_provider(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def _call_provider(
        self,
        *,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        if self.provider == "anthropic":
            return await self._call_anthropic(prompt, system, max_tokens, temperature)
        elif self.provider == "openai":
            return await self._call_openai(prompt, system, max_tokens, temperature)
        elif self.provider == "ollama":
            return await self._call_ollama(prompt, system, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def _call_anthropic(
        self, prompt: str, system: str, max_tokens: int, temperature: float
    ) -> LLMResponse:
        url = self.base_url or "https://api.anthropic.com"
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/v1/messages",
                json=body,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Anthropic API error {resp.status}: {text}")
                data = await resp.json()
                return LLMResponse(
                    content=data["content"][0]["text"],
                    model=data.get("model", self.model),
                    usage=data.get("usage", {}),
                )

    async def _call_openai(
        self, prompt: str, system: str, max_tokens: int, temperature: float
    ) -> LLMResponse:
        url = self.base_url or "https://api.openai.com"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"OpenAI API error {resp.status}: {text}")
                data = await resp.json()
                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data.get("model", self.model),
                    usage=data.get("usage", {}),
                )

    async def _call_ollama(
        self, prompt: str, system: str, max_tokens: int, temperature: float
    ) -> LLMResponse:
        url = self.base_url or "http://localhost:11434"
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            body["system"] = system

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/api/generate",
                json=body,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Ollama API error {resp.status}: {text}")
                data = await resp.json()
                return LLMResponse(
                    content=data.get("response", ""),
                    model=data.get("model", self.model),
                    usage={
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                    },
                )
