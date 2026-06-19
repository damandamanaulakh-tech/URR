"""Pluggable base-model layer.

Sourceborn is a *control layer around a base model* (your own brief). The engine
never calls a model directly — it calls this interface, so you can run it with:

* ``RuleBasedModel`` — the default. No API key, no network, fully deterministic.
  It does not fake intelligence; it reports structured reasoning so the whole
  pipeline is testable offline.
* ``ClaudeModel`` — uses your Claude key (env ``ANTHROPIC_API_KEY``) when you
  want real reasoning. Falls back gracefully if the SDK / key is absent.

Any object with ``.complete(system: str, prompt: str) -> str`` works.
"""

from __future__ import annotations

import os
from typing import Protocol


class BaseModel(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...


class RuleBasedModel:
    """Deterministic stand-in so the engine runs anywhere with no install."""

    name = "rule-based"

    def complete(self, system: str, prompt: str) -> str:
        # Echo a structured, honest stub. The engine's value (memory, pyramid,
        # URR, persona, wisdom) is real even when the base model is a stub.
        head = prompt.strip().splitlines()[0] if prompt.strip() else ""
        return (
            "[rule-based draft] "
            f"{head[:240]} "
            "— (plug in ClaudeModel via ANTHROPIC_API_KEY for full reasoning)"
        )


class ClaudeModel:
    """Adapter for Anthropic's API. Optional — only used if SDK + key present."""

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
            model=self.model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(b, "text", "") for b in msg.content)


def default_model() -> BaseModel:
    """Use Claude if a key is present, else the offline rule-based model."""
    claude = ClaudeModel()
    return claude if claude.available else RuleBasedModel()
