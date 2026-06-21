"""Halt -> Loop mapping (hard rule).

Every Halt Point must create at least one new loop before the current
stage/loop can close. The mapping below is the canonical one from
SBUR_Full_Engine_Spec section 3.3 and SB_Master_Core section 2.
"""

from __future__ import annotations

from .enums import HaltType, LoopType

# A halt can map to more than one candidate loop; the first is the default.
HALT_TO_LOOP: dict[HaltType, list[LoopType]] = {
    HaltType.EVIDENCE: [LoopType.EVIDENCE],
    HaltType.LANGUAGE: [LoopType.PATTERN, LoopType.INTENT_CONDITION_POWER],
    HaltType.LOGIC: [LoopType.CONTRADICTION, LoopType.FALSIFIER],
    HaltType.PRODUCT: [LoopType.PRODUCT_ROUTE, LoopType.REVIEW_VERIFICATION],
    HaltType.MYSTERY: [LoopType.MYSTERY],
    HaltType.STATUS: [LoopType.ADMIN_REVIEW],
    HaltType.SAFETY: [LoopType.ADMIN_REVIEW],
    HaltType.PUBLIC_CLAIM: [LoopType.PUBLIC_EXTRACTION],
    HaltType.REALITY: [LoopType.REALITY_CHECK],
    HaltType.CONTRADICTION: [LoopType.CONTRADICTION],
}


def loop_for_halt(halt: HaltType) -> LoopType:
    """Return the mandatory loop type for a given halt type."""
    candidates = HALT_TO_LOOP.get(halt)
    if not candidates:
        raise KeyError(f"No loop mapping for halt type: {halt}")
    return candidates[0]
