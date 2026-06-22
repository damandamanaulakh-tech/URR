"""Stage 3 — Doubt Engine, Falsifier, Witness Node (Principles 16 & 17).

The engine must attack its own strongest conclusion before delivery, name a
falsifier, and surface its own blind spots. Rule-based and offline; a model can
deepen each, but the discipline (it must bite sometimes) is real and testable.
"""

from __future__ import annotations

OVERCLAIM = ["always", "never", "everyone", "no one", "guaranteed", "obviously",
             "clearly", "proven", "certain", "undeniable", "impossible", "definitely"]


def doubt_engine(conclusion: str, has_live: bool, matched_count: int) -> dict:
    """Attack the conclusion. If it is fragile AND unsupported, the Doubt Engine
    'bites' — confidence drops and the engine should hold or re-loop."""
    low = conclusion.lower()
    fragilities: list[str] = []
    for w in OVERCLAIM:
        if w in low:
            fragilities.append(f"overclaim '{w}' — soften or support it")
    if not has_live:
        fragilities.append("no live fact grounding — may be stale or unverified")
    if matched_count < 1:
        fragilities.append("no matching example — pattern asserted, not precedented")
    bites = len(fragilities) >= 2
    return {
        "fragilities": fragilities,
        "bites": bites,
        "verdict": "fragile — hold or re-loop" if bites else "survives doubt for now",
    }


def falsifier(ask: str) -> str:
    """Every output carries a falsifier (Principle / Non-negotiable 8)."""
    return (f"What current fact or counterexample would show the opposite of "
            f"“{ask[:90]}”? If none can be named, treat the claim as OPEN.")


def witness(fired_nodes: list[str], dominant_lens: str, has_live: bool) -> list[str]:
    """What is the engine NOT seeing about itself right now?"""
    blind: list[str] = []
    if dominant_lens and dominant_lens != "none surfaced":
        blind.append(f"reading is colored by the '{dominant_lens}' lens — check the other five")
    if not has_live:
        blind.append("answering from memory/example only — no eyes on present fact")
    if len({n for n in fired_nodes if n.startswith('SB-')}) < 6:
        blind.append("shallow path — few nodes fired; may be under-thinking this")
    return blind or ["no obvious blind spot surfaced — stay skeptical anyway"]
