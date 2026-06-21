"""Core data structures for a Sourceborn run.

These are deliberately plain ``dataclasses`` (stdlib only) so the whole engine
runs with zero install and the data is trivially serialisable to JSON for the
file-based memory store.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

from .enums import (
    Classification,
    EvidenceTag,
    ForceFitRisk,
    PenetrationScore,
)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class RawSource:
    """Rule 14: Raw Source Never Changes. Captured exactly, then locked."""

    text: str
    origin: str = "chat"
    raw_source_id: str = field(default_factory=lambda: _id("RAW"))
    captured_at: str = field(default_factory=_now)
    locked: bool = False

    def lock(self) -> "RawSource":
        self.locked = True
        return self


@dataclass
class PointZero:
    """Unlimited starting position before forced selection. NOT current status."""

    raw_source_id: str
    literal_ask: str = ""
    hidden_goal: str = ""
    success_criteria: str = ""
    point_zero_id: str = field(default_factory=lambda: _id("PZ"))
    locked: bool = False
    carried_product: dict[str, Any] | None = None  # RGL: PZ in loop N carries product of N-1


@dataclass
class MemoryEntry:
    """A high-parameter memory record (Principle 4: Memory is High-Parameter).

    ``parameters`` can hold hundreds of axes; ``pyramid`` holds the Node -> Main
    -> Sub -> Micro filtering for this entry.
    """

    node_id: str
    raw_source_id: str
    content: str
    entry_id: str = field(default_factory=lambda: _id("MEM"))
    parameters: dict[str, Any] = field(default_factory=dict)
    pyramid: dict[str, list[str]] = field(
        default_factory=lambda: {"main": [], "sub": [], "micro": []}
    )
    classification: str = Classification.UNKNOWN.value
    evidence_tag: str = EvidenceTag.OPEN.value
    tags: list[str] = field(default_factory=list)         # Mystery, Invention, ...
    links: list[str] = field(default_factory=list)        # other entry/loop/node ids
    proof_debt: str = ""                                  # for SYNTHETIC items
    expiry: str = ""                                      # for SYNTHETIC items
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GapItem:
    description: str
    gap_type: str = "Evidence"      # Evidence|Logic|Domain|Safety|Mystery|Invention
    severity: str = "Medium"
    suggested_loop: str | None = None
    gap_id: str = field(default_factory=lambda: _id("GAP"))
    status: str = "open"
    created_at: str = field(default_factory=_now)


@dataclass
class ProofItem:
    claim: str
    evidence_type: str = ""
    evidence_reference: str = ""
    confidence: str = "Low"          # Low|Medium|High|Proven
    proof_id: str = field(default_factory=lambda: _id("PRF"))
    status: str = "tentative"        # tentative|verified|contradicted
    created_at: str = field(default_factory=_now)


@dataclass
class SyntheticTag:
    """Principle 3: Synthetic Must Be Tagged (proof debt + expiry)."""

    name: str
    value: str
    why_used: str
    risk: str = "Medium"
    proof_required: str = ""
    expiry: str = "end_of_run"


@dataclass
class URRPacket:
    """What a URR verification node returns to the SB tree."""

    urr_id: str
    sb_node_id: str
    classification: str = Classification.UNKNOWN.value
    evidence_tag: str = EvidenceTag.OPEN.value
    force_fit_risk: str = ForceFitRisk.LOW.value
    halt_triggered: bool = False
    halt_type: str | None = None
    risk_flags: list[str] = field(default_factory=list)
    new_parameters: list[str] = field(default_factory=list)
    recommended_action: str = "proceed"
    trace_note: str = ""


@dataclass
class Output:
    """A delivered result. Carries its backing (Principle: every word backed below)."""

    answer: str
    lanes: dict[str, Any] = field(default_factory=dict)
    evidence_tag: str = EvidenceTag.REVIEW.value
    classification: str = Classification.REVIEW_ONLY.value
    confidence: str = "Medium"
    reversibility: str = "Reversible"
    falsifier: str = ""
    penetration_score: str = PenetrationScore.SHALLOW.value
    open_question: str = ""
    public_safe: bool = False
    matched_examples: list[str] = field(default_factory=list)
    output_id: str = field(default_factory=lambda: _id("OUT"))
    created_at: str = field(default_factory=_now)


@dataclass
class TraceEntry:
    node_id: str
    action: str
    status: str = "running"
    halt: str | None = None
    note: str = ""
    at: str = field(default_factory=_now)
