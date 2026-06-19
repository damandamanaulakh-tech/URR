"""The clone layer — "it will clone me, and keep adding my way of answering".

This is the muscle memory of the brain. It holds:

* a **style profile** — the user's vocabulary lock (IN / OUT words), tone, and
  answering structure, so output sounds like the user, not like a generic model;
* a **growing example bank** — every (question -> the user's way of answering)
  pair, which compounds with use so the instrument sharpens over time.

It is data the user owns (plain JSON), separate from the reasoning engine, so the
*voice* can evolve independently of the *logic*.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any

from .models import _id, _now

# Vocabulary lock from ARD 3.1 (words the user's mind uses / refuses).
DEFAULT_IN_WORDS = [
    "Doubt", "Wound", "Pressure", "Witness", "Hunger", "Mask", "Loyalty",
    "Reality", "Pain", "Payoff", "Meaning", "Anchor", "Penetrate", "Hold",
    "Incubate", "Point Zero", "Wild Path", "Mystery", "Invention", "Source",
]
DEFAULT_OUT_WORDS = [
    "Stake", "Execution", "Kernel", "Tier", "Contract", "Throughput",
    "Pipeline", "Ship", "Deliverable", "best", "nice", "good (as target)",
]


@dataclass
class Example:
    question: str
    answer: str
    note: str = ""
    axes: dict[str, str] = field(default_factory=dict)
    example_id: str = field(default_factory=lambda: _id("EX"))
    created_at: str = field(default_factory=_now)


@dataclass
class StyleProfile:
    in_words: list[str] = field(default_factory=lambda: list(DEFAULT_IN_WORDS))
    out_words: list[str] = field(default_factory=lambda: list(DEFAULT_OUT_WORDS))
    tone: str = (
        "Direct. Top-down from the bigger picture. Preserve raw thought; never "
        "flatten ambition; classify instead of rejecting; admit gaps honestly."
    )
    structure: str = (
        "Lead with the deepest matching example, then the present fact, then a "
        "clean traceable answer. Keep it short unless depth is asked."
    )
    principles: list[str] = field(default_factory=lambda: [
        "Eternal example, present fact.",
        "More parameters, more outcome.",
        "Nothing rejected at intake; nothing claimed as fact without evidence.",
        "Human authority is absolute.",
    ])


class Persona:
    def __init__(self, root: str = ".sourceborn") -> None:
        self.path = os.path.join(root, "persona.json")
        os.makedirs(root, exist_ok=True)
        self.style = StyleProfile()
        self.examples: list[Example] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.style = StyleProfile(**data.get("style", {}))
            self.examples = [Example(**e) for e in data.get("examples", [])]

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {"style": asdict(self.style),
                 "examples": [asdict(e) for e in self.examples]},
                f, indent=2, ensure_ascii=False,
            )

    def learn(self, question: str, answer: str, note: str = "", **axes: str) -> str:
        """Add one of the user's examples. The clone compounds with every use."""
        ex = Example(question=question, answer=answer, note=note, axes=axes)
        self.examples.append(ex)
        self.save()
        return ex.example_id

    def recall(self, query: str, limit: int = 3) -> list[Example]:
        """Cheap keyword recall over the user's own examples (muscle memory)."""
        q = set(query.lower().split())
        scored = [
            (len(q & set((e.question + " " + e.answer).lower().split())), e)
            for e in self.examples
        ]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: s[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def voice_guidance(self) -> str:
        """Instructions injected into the base model so output sounds like the user."""
        return (
            f"Answer in this voice. TONE: {self.style.tone} "
            f"STRUCTURE: {self.style.structure} "
            f"USE words like: {', '.join(self.style.in_words[:12])}. "
            f"AVOID words like: {', '.join(self.style.out_words[:10])}. "
            f"PRINCIPLES: {' | '.join(self.style.principles)}"
        )
