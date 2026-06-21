"""Safety boundary (hard blocks + soft blocks).

From URR-07, SBUR spec section 3.6 and the Secureborn instruction. The engine
never *executes* harmful content, but it still maps the request safely (says
what the claim is, why execution is blocked, what can be discussed as theory).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Hard blocks: execution is refused outright (still mapped safely, never executed).
HARD_BLOCK_PATTERNS: dict[str, str] = {
    "weapon construction/use": r"\b(build|make|construct|assemble)\b.{0,40}\b(bomb|explosive|weapon|gun|firearm|nerve agent|bioweapon)\b",
    "harmful/illegal execution": r"\b(synthesi[sz]e|manufacture|cook)\b.{0,30}\b(meth|fentanyl|heroin|ricin|sarin)\b",
    "fraud execution": r"\b(how to)\b.{0,30}\b(launder money|forge|counterfeit|steal (a )?(card|identity))\b",
    "medical misuse": r"\b(lethal|fatal)\b.{0,20}\b(dose|overdose)\b",
    "guaranteed prediction": r"\bguarantee(d)?\b.{0,30}\b(win|profit|stock|bet|lottery)\b",
    "explicit sexual/nude generation": r"\b(generate|create|draw)\b.{0,30}\b(nude|explicit sexual|porn)\b",
}

# Soft blocks: allowed only as theory/history/fiction with a confirmation gate.
SOFT_BLOCK_TERMS: list[str] = [
    "extremis", "radicali", "self-harm", "suicide", "overthrow",
]


@dataclass
class SafetyVerdict:
    blocked: bool
    kind: str = "none"  # "hard" | "soft" | "none"
    reasons: list[str] = field(default_factory=list)
    safe_mapping: dict[str, str] = field(default_factory=dict)


def check(raw_text: str) -> SafetyVerdict:
    """Classify a raw request against the safety boundary."""
    text = raw_text.lower()
    hard_hits = [
        label
        for label, pattern in HARD_BLOCK_PATTERNS.items()
        if re.search(pattern, text)
    ]
    if hard_hits:
        return SafetyVerdict(
            blocked=True,
            kind="hard",
            reasons=hard_hits,
            safe_mapping={
                "what_the_claim_is": "Request touches a hard-blocked execution area.",
                "why_execution_is_blocked": "; ".join(hard_hits),
                "what_can_be_discussed_safely": (
                    "History, theory, mechanism-at-a-high-level, risk, contradiction, "
                    "and what evidence would be needed — never operational steps."
                ),
                "what_public_claim_is_not_allowed": "Any operational or how-to claim.",
            },
        )

    soft_hits = [t for t in SOFT_BLOCK_TERMS if t in text]
    if soft_hits:
        return SafetyVerdict(
            blocked=False,
            kind="soft",
            reasons=soft_hits,
            safe_mapping={
                "note": "Sensitive topic — handled as theory/history/fiction only, with a confirmation gate.",
            },
        )

    return SafetyVerdict(blocked=False, kind="none")
