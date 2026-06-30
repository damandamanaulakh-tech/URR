"""Core Gate — the six lenses (SB-10), made real.

Stage 2's heart: read the human under the words. Each lens surfaces a different
motive layer (ARD 3.1 / 7025 Core Gate). This is a rule-based reading that runs
with zero dependencies; a model-backed engine can enrich each lens, but the
structure, signals and dominant-lens logic are real and testable offline.

Affect is first-class data (Principle 15): feeling is read, not dismissed.
"""

from __future__ import annotations

import re

# lens -> signal words that hint the lens is active in the raw text
LENS_SIGNALS: dict[str, list[str]] = {
    "Mask & Payoff": ["look", "image", "prove", "impress", "status", "ego",
                      "appear", "credit", "respect", "seen"],
    "Wound & Threat": ["fail", "afraid", "fear", "hurt", "attack", "lose",
                       "threat", "rejected", "betray", "exposed"],
    "Loyalty & Drive": ["family", "team", "owe", "loyal", "promise", "duty",
                        "tribe", "belong", "protect", "for them"],
    "Desire & Fear": ["want", "wish", "crave", "hope", "dream", "scared",
                      "avoid", "need", "hunger"],
    "Pain & Payoff": ["pain", "cost", "sacrifice", "worth", "gain", "reward",
                      "struggle", "price", "suffer"],
    "Meaning & Identity": ["who am i", "meaning", "purpose", "identity", "real",
                           "become", "self", "matter", "legacy", "soul"],
}

LENS_READINGS: dict[str, str] = {
    "Mask & Payoff": "what image is being protected, and what does keeping it pay off?",
    "Wound & Threat": "what old wound or threat is this defending against?",
    "Loyalty & Drive": "whose approval / which loyalty is quietly driving this?",
    "Desire & Fear": "what is truly wanted, and what is feared underneath it?",
    "Pain & Payoff": "what pain is being carried, and what is the hidden gain?",
    "Meaning & Identity": "who must the asker be for this to matter?",
}


def six_lenses(text: str) -> dict:
    """Run the six lenses over raw text. Returns per-lens signals + reading and
    the dominant lens (the one with the strongest signal)."""
    low = text.lower()
    lenses: dict[str, dict] = {}
    for lens, words in LENS_SIGNALS.items():
        # whole-word match only — so "credit" in a bill or "build" inside
        # "Building" no longer trips a psychological lens (the bug that
        # psychoanalysed a billing spreadsheet).
        hits = [w for w in words
                if re.search(r"\b" + re.escape(w) + r"\b", low)]
        lenses[lens] = {
            "signals": hits,
            "active": bool(hits),
            "reading": LENS_READINGS[lens] if hits
            else "no strong signal on this lens (kept open, not forced)",
        }
    dominant = max(lenses.items(), key=lambda kv: len(kv[1]["signals"]))
    dominant_lens = dominant[0] if dominant[1]["signals"] else "none surfaced"
    return {
        "lenses": lenses,
        "dominant_lens": dominant_lens,
        "active_count": sum(1 for v in lenses.values() if v["active"]),
    }
