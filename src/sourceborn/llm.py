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
import urllib.error
import urllib.request
from typing import Protocol


class BaseModel(Protocol):
    name: str
    available: bool
    def complete(self, system: str, prompt: str) -> str: ...


def _post_json(url: str, headers: dict, payload: dict, timeout: int = 90) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as exc:        # surface the provider's real message
        body = exc.read().decode("utf-8", "ignore")
        try:
            j = json.loads(body)
        except Exception:
            j = {"error": {"message": (body[:300] or str(exc))}}
        return j if isinstance(j, dict) and "error" in j else {"error": j}


class RuleBasedModel:
    """Deterministic stand-in so the engine runs anywhere with no key."""

    name = "offline"
    available = True

    def complete(self, system: str, prompt: str) -> str:
        head = prompt.strip().splitlines()[0] if prompt.strip() else ""
        return ("[offline draft] " + head[:240]
                + " — add an API key in Render's Environment tab to switch on real reasoning")

    def complete_vision(self, system: str, prompt: str, image_b64: str,
                        mime: str = "image/png") -> str:
        return ("[offline] image received — add an API key (Grok/OpenRouter/Claude) "
                "in Render's Environment tab to switch on real vision")


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
            if data.get("error"):
                err = data["error"]
                return f"[claude error: {err.get('message') if isinstance(err, dict) else err}]"
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text")
            return text or "[claude returned no text]"
        except Exception as exc:
            return f"[claude error: {exc}] " + RuleBasedModel().complete(system, prompt)

    def complete_vision(self, system: str, prompt: str, image_b64: str,
                        mime: str = "image/png") -> str:
        if not self.key:
            return RuleBasedModel().complete_vision(system, prompt, image_b64, mime)
        try:
            data = _post_json(
                "https://api.anthropic.com/v1/messages",
                {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
                {"model": self.model, "max_tokens": 4000, "system": system,
                 "messages": [{"role": "user", "content": [
                     {"type": "image", "source": {"type": "base64",
                      "media_type": mime, "data": image_b64}},
                     {"type": "text", "text": prompt}]}]},
            )
            if data.get("error"):
                err = data["error"]
                return f"[claude vision error: {err.get('message') if isinstance(err, dict) else err}]"
            return "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text") or "[claude returned no text]"
        except Exception as exc:
            return f"[claude vision error: {exc}]"


class _OpenAICompatible:
    """Shared adapter for OpenAI and xAI/Grok (both OpenAI-compatible)."""

    name = "openai"
    _env_key = "OPENAI_API_KEY"
    _url = "https://api.openai.com/v1/chat/completions"
    _model_env = "OPENAI_MODEL"
    _default_model = "gpt-4o"
    _extra_headers: dict = {}

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
                {"Authorization": f"Bearer {self.key}", "content-type": "application/json",
                 **self._extra_headers},
                {"model": self.model, "max_tokens": 4000,
                 "messages": [{"role": "system", "content": system},
                              {"role": "user", "content": prompt}]},
            )
            if isinstance(data, dict) and data.get("error"):
                err = data["error"]
                return f"[{self.name} error: {err.get('message') if isinstance(err, dict) else err}]"
            return (data.get("choices", [{}])[0].get("message", {}).get("content")
                    or f"[{self.name} returned no text]")
        except Exception as exc:
            return f"[{self.name} error: {exc}] " + RuleBasedModel().complete(system, prompt)

    def complete_vision(self, system: str, prompt: str, image_b64: str,
                        mime: str = "image/png") -> str:
        if not self.key:
            return RuleBasedModel().complete_vision(system, prompt, image_b64, mime)
        try:
            data = _post_json(
                self._url,
                {"Authorization": f"Bearer {self.key}", "content-type": "application/json",
                 **self._extra_headers},
                {"model": os.environ.get("SB_VISION_MODEL", self.model), "max_tokens": 4000,
                 "messages": [{"role": "system", "content": system},
                              {"role": "user", "content": [
                                  {"type": "text", "text": prompt},
                                  {"type": "image_url", "image_url": {
                                      "url": f"data:{mime};base64,{image_b64}"}}]}]},
            )
            if isinstance(data, dict) and data.get("error"):
                err = data["error"]
                return f"[{self.name} vision error: {err.get('message') if isinstance(err, dict) else err}]"
            return (data.get("choices", [{}])[0].get("message", {}).get("content")
                    or f"[{self.name} returned no text]")
        except Exception as exc:
            return f"[{self.name} vision error: {exc}]"


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
    _extra_headers = {"HTTP-Referer": "https://sourceborn.onrender.com",
                      "X-Title": "Sourceborn"}


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
    order = ([pref] if pref in _REGISTRY else []) + ["grok", "openrouter", "openai", "claude"]
    for key in order:
        m = _REGISTRY[key]()
        if getattr(m, "available", False):
            return m
    return RuleBasedModel()


def generate_image(prompt: str) -> dict:
    """Text -> image via the first available provider key (one key, no new dep).
    Prefers xAI (grok-2-image), then OpenAI. Returns {"url"|"b64"} or {"error"}.
    Override the model with SB_IMAGE_MODEL."""
    xai = os.environ.get("XAI_API_KEY")
    oai = os.environ.get("OPENAI_API_KEY")
    if xai:
        url = "https://api.x.ai/v1/images/generations"
        headers = {"Authorization": f"Bearer {xai}", "content-type": "application/json"}
        payload = {"model": os.environ.get("SB_IMAGE_MODEL", "grok-2-image"),
                   "prompt": prompt, "n": 1}
    elif oai:
        url = "https://api.openai.com/v1/images/generations"
        headers = {"Authorization": f"Bearer {oai}", "content-type": "application/json"}
        payload = {"model": os.environ.get("SB_IMAGE_MODEL", "gpt-image-1"),
                   "prompt": prompt, "n": 1}
    else:
        return {"error": "no image key — set XAI_API_KEY or OPENAI_API_KEY in Render"}
    try:
        d = _post_json(url, headers, payload)
    except Exception as exc:
        return {"error": str(exc)}
    if isinstance(d, dict) and d.get("error"):
        err = d["error"]
        return {"error": err.get("message") if isinstance(err, dict) else str(err)}
    item = (d.get("data") or [{}])[0]
    return {"url": item.get("url"), "b64": item.get("b64_json"), "prompt": prompt}
