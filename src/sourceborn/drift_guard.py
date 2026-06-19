"""Anti-divert guard — the engine's own protection against drift.

This is your own principle in code: **Reality Re-Anchor** (Principle 20),
**Trajectory Tracker** (catch drift mid-run), and **Drift Control** (URR-07). It
keeps the engine bound to Point Zero so a long run cannot quietly wander off the
user's original ask.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# URR-07 drift-control rules (what the engine must NOT do).
DRIFT_CONTROL_RULES: tuple[str, ...] = (
    "Do not flatter or blindly agree.",
    "Do not kill the wild thought.",
    "Do not mark theory as proven.",
    "Do not force public-safe wording unless asked.",
    "Do not invent links between unrelated items.",
    "Do not change core without showing the proposed change first.",
    "Do not remove Mystery or Invention.",
    "Do not treat a Halt Point as failure.",
    "Do not treat Point Zero as current real status.",
    "Do not force a Product early.",
)


@dataclass
class TrajectoryTracker:
    """Logs where a run started vs where it is now; flags within-run drift."""

    start_intent: str
    pivots: list[str] = field(default_factory=list)

    def pivot(self, note: str) -> None:
        self.pivots.append(note)

    def drift_score(self, current_text: str) -> float:
        """0.0 = on-target, 1.0 = fully diverted (cheap lexical overlap)."""
        start = set(self.start_intent.lower().split())
        cur = set(current_text.lower().split())
        if not start:
            return 0.0
        overlap = len(start & cur) / len(start)
        return round(1.0 - overlap, 2)


@dataclass
class AnchorVerdict:
    on_target: bool
    drift_score: float
    note: str


def reality_reanchor(point_zero_ask: str, conclusion: str,
                     threshold: float = 0.85) -> AnchorVerdict:
    """Reality Re-Anchor: does the conclusion still answer the original ask?

    Returns a verdict the engine records in its trace. High drift → the engine
    flags it rather than delivering a diverted answer as if it were on-target.
    """
    score = TrajectoryTracker(point_zero_ask).drift_score(conclusion)
    on_target = score < threshold
    note = ("anchored to Point Zero" if on_target
            else "DRIFT: conclusion strayed from original ask — re-anchor")
    return AnchorVerdict(on_target=on_target, drift_score=score, note=note)
