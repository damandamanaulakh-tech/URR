"""Pluggable base-model layer — stdlib HTTP, zero dependencies.

Sourceborn is a *control layer around a base model*. The engine never calls a
provider directly — it calls this interface. Adapters here use the providers'
HTTPS APIs via stdlib ``urllib`` only, so the whole app still deploys to Render
with **no build step and no SDK install** — the moment a key is set as an env
var, that model goes live.

* ``RuleBasedModel`` — default. No key, no network. Safe offline placeholder.
* ``ClaudeModel``    — Anthropic Messages API (``ANTHROPIC_API_KEY``).
* ``GrokModel``      — xAI, OpenAI-compatible (``XAI_API_KEY``).
* ``OpenAIModel``    — OpenAI Chat Completions (``OPENAI_API_KEY``).

Model IDs default to the latest (``claude-opus-4-8`` etc.) and can be overridden
per provider via env (``ANTHROPIC_MODEL`` / ``XAI_MODEL`` / ``OPENAI_MODEL``)
without a code change. ``available`` is simply "is the key present" — no import
to fail, so a configured key is never silently ignored.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Protocol


class BaseModel(Protocol):
    name: str
    available: bool
    def complete(self, system: str, prompt: str) -> str: ...


def _post_json(url: str, headers: dict, payload: dict, timeout: int = 90) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


class RuleBasedModel:
    """Deterministic stand-in so the engine runs anywhere with no key."""

    name = "offline"
    available = True

    def complete(self, system: str, prompt: str) -> str:
        head = prompt.strip().splitlines()[0] if prompt.strip() else ""
        return ("[offline draft] " + head[:240]
                + " — add an API key in Render's Environment tab to switch on real reasoning")


class ClaudeModel:
    """Anthropic Messages API over HTTPS (no SDK). Model: claude-opus-4-8."""

    name = "claude"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
        self.key = os.environ.get("ANTHROPIC_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self.key)

    def complete(self, system: str, prompt: str) -> str:
        if not self.key:
            return RuleBasedModel().complete(system, prompt)
        try:
            data = _post_json(
                "https://api.anthropic.com/v1/messages",
                {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
                {"model": self.model, "max_tokens": 4000, "system": system,
                 "messages": [{"role": "user", "content": prompt}]},
            )
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text")
            return text or "[claude returned no text]"
        except Exception as exc:
            return f"[claude error: {exc}] " + RuleBasedModel().complete(system, prompt)


class _OpenAICompatible:
    """Shared adapter for OpenAI and xAI/Grok (both OpenAI-compatible)."""

    name = "openai"
    _env_key = "OPENAI_API_KEY"
    _url = "https://api.openai.com/v1/chat/completions"
    _model_env = "OPENAI_MODEL"
    _default_model = "gpt-4o"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get(self._model_env, self._default_model)
        self.key = os.environ.get(self._env_key)

    @property
    def available(self) -> bool:
        return bool(self.key)

    def complete(self, system: str, prompt: str) -> str:
        if not self.key:
            return RuleBasedModel().complete(system, prompt)
        try:
            data = _post_json(
                self._url,
                {"Authorization": f"Bearer {self.key}", "content-type": "application/json"},
                {"model": self.model, "max_tokens": 4000,
                 "messages": [{"role": "system", "content": system},
                              {"role": "user", "content": prompt}]},
            )
            return data["choices"][0]["message"].get("content") or f"[{self.name} returned no text]"
        except Exception as exc:
            return f"[{self.name} error: {exc}] " + RuleBasedModel().complete(system, prompt)


class OpenAIModel(_OpenAICompatible):
    name = "openai"
    _env_key = "OPENAI_API_KEY"
    _url = "https://api.openai.com/v1/chat/completions"
    _model_env = "OPENAI_MODEL"
    _default_model = "gpt-4o"


class GrokModel(_OpenAICompatible):
    """xAI Grok — unrestricted/raw, real-time data (your 'New setup' stack)."""

    name = "grok"
    _env_key = "XAI_API_KEY"
    _url = "https://api.x.ai/v1/chat/completions"
    _model_env = "XAI_MODEL"
    _default_model = "grok-4"


class OpenRouterModel(_OpenAICompatible):
    """OpenRouter — one key, many models (OpenAI-compatible). Pick the routed
    model with OPENROUTER_MODEL (e.g. ``anthropic/claude-3.5-sonnet``)."""

    name = "openrouter"
    _env_key = "OPENROUTER_API_KEY"
    _url = "https://openrouter.ai/api/v1/chat/completions"
    _model_env = "OPENROUTER_MODEL"
    _default_model = "openai/gpt-4o"


_REGISTRY = {
    "offline": RuleBasedModel,
    "claude": ClaudeModel,
    "grok": GrokModel,
    "openai": OpenAIModel,
    "openrouter": OpenRouterModel,
}


def get_model(name: str) -> BaseModel:
    cls = _REGISTRY.get((name or "offline").lower(), RuleBasedModel)
    m = cls()
    return m if getattr(m, "available", True) else RuleBasedModel()


def model_status() -> dict[str, bool]:
    """Which models are usable right now (keys present)? Drives the UI dropdown."""
    out = {"offline": True}
    for key in ("claude", "grok", "openai", "openrouter"):
        try:
            out[key] = bool(getattr(_REGISTRY[key](), "available", False))
        except Exception:
            out[key] = False
    return out


def default_model() -> BaseModel:
    """Pick the default model. Honour SB_DEFAULT_MODEL first (e.g. "grok" when
    that's the key with credit), then fall back through the usual order."""
    pref = os.environ.get("SB_DEFAULT_MODEL", "").strip().lower()
    order = ([pref] if pref in _REGISTRY else []) + ["claude", "grok", "openai", "openrouter"]
    for key in order:
        m = _REGISTRY[key]()
        if getattr(m, "available", False):
            return m
    return RuleBasedModel()
