"""Parameters — the heart of the engine.

Two things live here:

1. ``PARAMETER_BANK`` — the 64 canonical parameters (P001-P064) from the
   ARD Parameter Bank. These are the axes the engine *stores* about anything.

2. ``COMPARISON_AXES`` — the extensible comparison axes from
   SOURCEBORN_PRINCIPLE section V. The engine's law is literal:
   **more parameters of comparison -> more outcome.** New axes can be appended
   forever without changing the engine's shape.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    code: str
    name: str
    group: str


# --- The 64-parameter bank (ARD Parameter Bank P001-P064) -----------------
PARAMETER_BANK: tuple[Parameter, ...] = (
    Parameter("P001", "Surface Intent", "Intent"),
    Parameter("P002", "Hidden Intent", "Intent"),
    Parameter("P003", "Raw Visual Signal", "Signal"),
    Parameter("P004", "First Affect", "Affect"),
    Parameter("P005", "Emotional Driver", "Affect"),
    Parameter("P006", "Pressure Source", "Pressure"),
    Parameter("P007", "Protected Core", "Human Shadow"),
    Parameter("P008", "Mask Layer", "Human Shadow"),
    Parameter("P009", "Wound Layer", "Human Shadow"),
    Parameter("P010", "Payoff Layer", "Human Shadow"),
    Parameter("P011", "Cost Layer", "Human Shadow"),
    Parameter("P012", "Loyalty Layer", "Human Shadow"),
    Parameter("P013", "Desire Layer", "Human Shadow"),
    Parameter("P014", "Fear Layer", "Human Shadow"),
    Parameter("P015", "Identity Lock", "Identity"),
    Parameter("P016", "Role Capture", "Identity"),
    Parameter("P017", "Human Vessel", "Identity"),
    Parameter("P018", "King Action", "Action"),
    Parameter("P019", "Bloodline Pressure", "Pressure"),
    Parameter("P020", "Victory Pressure", "Pressure"),
    Parameter("P021", "Travel Pressure", "Pressure"),
    Parameter("P022", "Death/Rebirth Echo", "Transformation"),
    Parameter("P023", "Divine Pressure", "Pressure"),
    Parameter("P024", "Symbol Function", "Symbol"),
    Parameter("P025", "Transition Logic", "Transformation"),
    Parameter("P026", "Loop Trigger", "Loop"),
    Parameter("P027", "Exit Condition", "Loop"),
    Parameter("P028", "False Closure", "Loop"),
    Parameter("P029", "Missing Piece", "Gap"),
    Parameter("P030", "Silence Signal", "Gap"),
    Parameter("P031", "Distortion Field", "Risk"),
    Parameter("P032", "Official Story", "Reading"),
    Parameter("P033", "Forbidden Reading", "Reading"),
    Parameter("P034", "Myth Reading", "Reading"),
    Parameter("P035", "Trauma Reading", "Reading"),
    Parameter("P036", "Political Reading", "Reading"),
    Parameter("P037", "Family Reading", "Reading"),
    Parameter("P038", "Ritual Reading", "Reading"),
    Parameter("P039", "Psychological Reading", "Reading"),
    Parameter("P040", "Machine Reading", "Reading"),
    Parameter("P041", "Prison/Temple Split", "Reading"),
    Parameter("P042", "Fact Layer", "Evidence"),
    Parameter("P043", "Review Layer", "Evidence"),
    Parameter("P044", "Synthetic Layer", "Evidence"),
    Parameter("P045", "Promotion Test", "Evidence"),
    Parameter("P046", "Falsifier", "Evidence"),
    Parameter("P047", "Doubt Attack", "Doubt"),
    Parameter("P048", "Witness Check", "Doubt"),
    Parameter("P049", "Emotional Bias Check", "Doubt"),
    Parameter("P050", "Pattern Bias Check", "Doubt"),
    Parameter("P051", "Depth Score", "Score"),
    Parameter("P052", "Non-Resolution", "Score"),
    Parameter("P053", "Raw Thought Preservation", "Integrity"),
    Parameter("P054", "Sequence Reconstruction", "Integrity"),
    Parameter("P055", "Risk Flag", "Risk"),
    Parameter("P056", "Public/Private Boundary", "Boundary"),
    Parameter("P057", "Rumor Cage", "Boundary"),
    Parameter("P058", "Confidence", "Score"),
    Parameter("P059", "Reversibility", "Score"),
    Parameter("P060", "Evidence Delta", "Evidence"),
    Parameter("P061", "Symbol Cost", "Cost"),
    Parameter("P062", "Crown Cost", "Cost"),
    Parameter("P063", "Memory Storage", "Memory"),
    Parameter("P064", "Recursion Engine", "Loop"),
)

# Master formula the parameters serve (ARD Parameter Bank):
MASTER_FORMULA = (
    "Raw Symbol -> Role -> Pressure -> Emotion -> Action "
    "-> Transformation -> Cost -> Loop -> Evidence Status"
)


# --- Comparison axes (SOURCEBORN_PRINCIPLE V) — extensible forever ---------
# Each axis is one way the engine compares a question to its deepest example.
# Law: add axes -> multiply outcome.
COMPARISON_AXES: list[str] = [
    "Intent",            # what is truly being asked, under the words
    "Pattern",           # structure, recurrence, what repeats / breaks
    "Motive/Shadow",     # Mask&Payoff, Wound&Threat, Loyalty&Drive
    "Precedent/Archetype",  # oldest example that already holds the pattern
    "Moral/Sacred line",  # time-tested ethical anchor
    "Consequence",       # what the answer does to reader/world/future
    "Time",              # worsens under pressure? wait/incubate?
    "Scale",             # trivial vs existential
    "Opposite/Inversion",  # argue the exact opposite as adversary
    "Falsifier",         # external fact that would prove it wrong
    "Simplicity/Key-in-hand",  # is the obvious answer already in hand
    "Emotion",           # fear, love, betrayal, survival as live variables
    "Power/Condition",   # who holds power, under what conditions
]


def add_comparison_axis(axis: str) -> None:
    """Grow the engine: add a new axis of comparison (more axes, more outcome)."""
    if axis not in COMPARISON_AXES:
        COMPARISON_AXES.append(axis)


def parameter_groups() -> dict[str, list[Parameter]]:
    """Return the 64 parameters grouped by their group label."""
    groups: dict[str, list[Parameter]] = {}
    for p in PARAMETER_BANK:
        groups.setdefault(p.group, []).append(p)
    return groups
