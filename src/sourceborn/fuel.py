"""Stage 6 — Synthetic Fuel Injector (caged).

When the engine stalls (no data, contradiction, wrong frame), it does not fake
certainty — it injects ONE of five reality-warping fuels, tagged ``[SYNTHETIC]``
with proof-debt + expiry (Principle 3), and keeps moving. The stall is diagnosed
first so the right fuel is chosen.
"""

from __future__ import annotations

# stall -> the fuel that best breaks it (7025 stall-diagnostic table)
STALL_FUEL = {
    "Data-stall": "Hypothetical Simulation",
    "Logic-stall": "Counterfactual Friction",
    "Frame-stall": "Apostatic Inversion",
    "Complexity-stall": "Working Fiction",
    "default": "Heuristic Fiction",
}


def diagnose_stall(halts: list[str], has_live: bool, matched_count: int,
                   doubt_bites: bool) -> str | None:
    """Return the stall type, or None if the engine isn't actually stuck."""
    if "Evidence" in halts and not has_live:
        return "Data-stall"
    if "Logic" in halts or "Contradiction" in halts:
        return "Logic-stall"
    if matched_count == 0:
        return "Frame-stall"
    if doubt_bites:
        return "Complexity-stall"
    return None


def inject(stall: str, ask: str) -> dict:
    """Produce one caged synthetic fuel for the stall. Always tagged + expiring."""
    fuel = STALL_FUEL.get(stall, STALL_FUEL["default"])
    return {
        "stall": stall,
        "fuel": fuel,
        "synthetic_tag": {
            "name": fuel,
            "value": f"provisional frame for “{ask[:60]}”",
            "why_used": f"engine hit {stall}; forcing motion without faking fact",
            "proof_required": "promote only when evidence supports it",
            "expiry": "end_of_run",
        },
    }
