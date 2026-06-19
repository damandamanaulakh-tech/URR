"""Pluggable base-model layer.

Sourceborn is a *control layer around a base model* (your own brief). The engine
never calls a model directly — it calls this interface, so you can run it with:

* ``RuleBasedModel`` — default. No key, no network, fully deterministic. It does
  not fake intelligence; it returns a structured stub so the pipeline is testable
  offline (the engine's value — memory, pyramid, URR, persona, wisdom — is real
  even when the base model is a stub).
* ``ClaudeModel`` / ``GrokModel`` / ``OpenAIModel`` — use your keys when you want
  real reasoning. Each falls back to the stub if its SDK / key is absent.

Pick per request with ``get_model("claude" | "grok" | "openai" | "offline")``.
Any object with ``.complete(system, prompt) -> str`` works.
"""

from __future__ import annotations

import os
from typing import Protocol


class BaseModel(Protocol):
    name: str
    available: bool
    def complete(self, system: str, prompt: str) -> str: ...


class RuleBasedModel:
    """Deterministic stand-in so the engine runs anywhere with no install."""

    name = "offline"
    available = True

    def complete(self, system: str, prompt: str) -> str:
        head = prompt.strip().splitlines()[0] if prompt.strip() else ""
        return (
            "[offline draft] "
            f"{head[:240]} "
            "— (select Claude/Grok and set its API key for full reasoning)"
        )


class ClaudeModel:
    """Anthropic adapter. Used only if the SDK + ANTHROPIC_API_KEY are present."""

    name = "claude"

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self._client = None
        try:
            import anthropic  # type: ignore
            key = os.environ.get("ANTHROPIC_API_KEY")
            if key:
                self._client = anthropic.Anthropic(api_key=key)
        except Exception:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(self, system: str, prompt: str) -> str:
        if not self._client:
            return RuleBasedModel().complete(system, prompt)
        msg = self._client.messages.create(
            model=self.model, max_tokens=2000, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(b, "text", "") for b in msg.content)


class _OpenAICompatible:
    """Shared adapter for OpenAI and xAI/Grok (both OpenAI-compatible)."""

    name = "openai"
    _env_key = "OPENAI_API_KEY"
    _base_url: str | None = None
    _model = "gpt-4o"

    def __init__(self, model: str | None = None) -> None:
        if model:
            self._model = model
        self._client = None
        try:
            import openai  # type: ignore
            key = os.environ.get(self._env_key)
            if key:
                kwargs = {"api_key": key}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = openai.OpenAI(**kwargs)
        except Exception:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(self, system: str, prompt: str) -> str:
        if not self._client:
            return RuleBasedModel().complete(system, prompt)
        resp = self._client.chat.completions.create(
            model=self._model, max_tokens=2000,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


class OpenAIModel(_OpenAICompatible):
    name = "openai"
    _env_key = "OPENAI_API_KEY"
    _base_url = None
    _model = "gpt-4o"


class GrokModel(_OpenAICompatible):
    """xAI Grok — unrestricted/raw, real-time data (your 'New setup' stack)."""

    name = "grok"
    _env_key = "XAI_API_KEY"
    _base_url = "https://api.x.ai/v1"
    _model = "grok-2-latest"


_REGISTRY = {
    "offline": RuleBasedModel,
    "claude": ClaudeModel,
    "grok": GrokModel,
    "openai": OpenAIModel,
}


def get_model(name: str) -> BaseModel:
    cls = _REGISTRY.get((name or "offline").lower(), RuleBasedModel)
    m = cls()
    return m if getattr(m, "available", True) else RuleBasedModel()


def model_status() -> dict[str, bool]:
    """Which models are usable right now (keys present)? Drives the UI dropdown."""
    out = {"offline": True}
    for key in ("claude", "grok", "openai"):
        try:
            out[key] = bool(getattr(_REGISTRY[key](), "available", False))
        except Exception:
            out[key] = False
    return out


def default_model() -> BaseModel:
    for key in ("claude", "grok", "openai"):
        m = _REGISTRY[key]()
        if getattr(m, "available", False):
            return m
    return RuleBasedModel()
