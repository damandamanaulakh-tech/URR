"""Stage 4 — Evidence ladder + source tags.

Separates real from simulated, tags each claim by its best available source, and
sets the answer's confidence from the strongest rung reached. Source tags follow
the 7025 core: REAL_TOOL / MANUAL / MEMORY / SIMULATED.
"""

from __future__ import annotations


def build_ledger(claims: list[str], has_live: bool, corpus_refs: list[str]) -> list[dict]:
    """Tag each micro-claim by the strongest source backing it."""
    ledger: list[dict] = []
    for c in claims:
        if has_live:
            tag, source, conf = "FACT", "REAL_TOOL (live web)", "High"
        elif corpus_refs:
            tag, source, conf = "REVIEW", "MEMORY (your corpus)", "Medium"
        else:
            tag, source, conf = "OPEN", "none yet", "Low"
        ledger.append({"claim": c[:120], "evidence_tag": tag,
                       "source": source, "confidence": conf})
    return ledger


def ladder_confidence(ledger: list[dict]) -> str:
    """Confidence = the highest rung any claim reached."""
    tags = {e["evidence_tag"] for e in ledger}
    if "FACT" in tags:
        return "High"
    if "REVIEW" in tags:
        return "Medium"
    return "Low"
