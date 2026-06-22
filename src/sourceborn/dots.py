"""Stage 5 — Dot Connection + merge proposals (Principles 5 & 8).

The "click": when the same fed source recurs across different parts of a
question, that recurrence is a cross-connection. A merge is proposed only when
several strong connections converge (merge only on real value), and any
synthetic-heavy merge is flagged for the human gate.
"""

from __future__ import annotations

from collections import Counter


def dot_connections(per_part_refs: list[list[str]]) -> list[dict]:
    """A ref appearing for more than one micro-question is a connection."""
    counter: Counter[str] = Counter()
    for refs in per_part_refs:
        for r in set(refs):
            counter[r] += 1
    connections = [{"ref": r, "appears_in": n} for r, n in counter.items() if n > 1]
    connections.sort(key=lambda c: c["appears_in"], reverse=True)
    return connections


def merge_proposal(connections: list[dict]) -> dict | None:
    """Propose a merge only when >=2 sources converge (real added value)."""
    if len(connections) < 2:
        return None
    return {
        "contributing": [c["ref"] for c in connections[:4]],
        "insight": "these sources recur across the question's parts — "
                   "candidate unifying pattern",
        "needs_human": True,   # human gate before a merge is accepted
        "status": "proposed",
    }
