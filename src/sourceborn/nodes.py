"""The node map: 70 SB points across 8 stages + 25 URR points.

This is the canonical structure from ARD_RGL_7025 (the "Omni" core). Every node
is a *local brain* (see ``memory.NodeBrain``) with pyramid filtering
(Node -> 5-10 Main -> 10-20 Sub -> 20-30 Micro). The engine runs SB points in
sequence with URR verification gates interleaved, and any node can loop back to
any earlier node (full interconnection).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SBNode:
    sb_id: str          # e.g. "SB-01"
    name: str
    stage: int          # 1..8
    purpose: str = ""


@dataclass(frozen=True)
class URRNode:
    urr_id: str         # e.g. "URR-08"
    name: str
    triggers: str = ""


@dataclass(frozen=True)
class Stage:
    number: int
    name: str
    sb_range: tuple[int, int]
    focus: str


STAGES: tuple[Stage, ...] = (
    Stage(1, "Foundation & Intake", (1, 8), "Lock raw source, strip noise, classify domain, first memory write"),
    Stage(2, "Human Core & Psychology", (9, 18), "Affect, Core Gate 6 lenses, shadow, identity, power, wounds"),
    Stage(3, "Truth, Doubt & Pressure", (19, 28), "Truth pressure, Doubt Engine, Falsifier, Witness, contradictions"),
    Stage(4, "Evidence & Validation", (29, 36), "Evidence ledger, source tags, domain audit, live grounding"),
    Stage(5, "Connection, Dot & Memory", (37, 44), "Dot connection, cross-domain fusion, merges, new parameters"),
    Stage(6, "Synthetic, Invention & New Parameters", (45, 52), "Synthetic fuel, invention seeds, parameter generation"),
    Stage(7, "Risk, Ethics & Human Control", (53, 60), "Risk gate, logic walls, override ledger, reality re-anchor"),
    Stage(8, "Output, Memory Update & Brain Maintenance", (61, 70), "Master log, weekly brain update, final output, human halt"),
)

# The 70 SB points. Where the 7025 core names a node explicitly it is used;
# the remainder are named from their stage role so the map is complete and runnable.
SB_NODES: tuple[SBNode, ...] = (
    # Stage 1 — Foundation & Intake
    SBNode("SB-01", "Point Zero Lock", 1, "Lock the original raw source without any change"),
    SBNode("SB-02", "Noise & Static Stripper", 1, "Separate Fact/Feeling/Assumption/Pressure/Claim/Mystery/Invention Seed/Command"),
    SBNode("SB-03", "Source Domain Classifier", 1, "Identify domain, connect relevant data banks"),
    SBNode("SB-04", "Raw Source Preservation", 1, "Ensure original input can never be altered later"),
    SBNode("SB-05", "Initial Parameter Mapping", 1, "Check existing parameters, flag what does not fit"),
    SBNode("SB-06", "Data Bank Connector", 1, "Link external paid + free research sources"),
    SBNode("SB-07", "First Memory Write", 1, "Create first structured high-parameter memory entry"),
    SBNode("SB-08", "Intake Completion Gate", 1, "Confirm intake is clean before moving forward"),
    # Stage 2 — Human Core & Psychology
    SBNode("SB-09", "Affect & Intent Ledger", 2, "Emotional current, hidden motives, small intent feeds"),
    SBNode("SB-10", "Core Gate — Six Lenses", 2, "Mask/Payoff, Wound/Threat, Loyalty/Drive, Desire/Fear, Pain/Payoff, Meaning/Identity"),
    SBNode("SB-11", "Human Shadow Gate", 2, "What the user is protecting, avoiding, not saying"),
    SBNode("SB-12", "Hidden Intent Feed Detector", 2, "Detect small hidden intent feeds"),
    SBNode("SB-13", "Emotional Drama Processor", 2, "Process emotional drama as usable data"),
    SBNode("SB-14", "Sacred / Cultural Anchor", 2, "Bring in sacred, cultural, religious anchors"),
    SBNode("SB-15", "Identity & Meaning Analyzer", 2, "Analyze identity and meaning"),
    SBNode("SB-16", "Power & Control Mapper", 2, "Map power and control dynamics"),
    SBNode("SB-17", "Wound & Threat Examiner", 2, "Deeply examine wounds and threats"),
    SBNode("SB-18", "Human Layer Completion", 2, "Complete human layer before truth testing"),
    # Stage 3 — Truth, Doubt & Pressure
    SBNode("SB-19", "Truth Pressure Test", 3, "What truth is this system avoiding?"),
    SBNode("SB-20", "Doubt Engine", 3, "Systematically break the strongest conclusion"),
    SBNode("SB-21", "Falsifier", 3, "Actively test for falsification"),
    SBNode("SB-22", "Witness Node", 3, "Surface what the engine itself is blind to"),
    SBNode("SB-23", "Contradiction Finder", 3, "Find contradictions"),
    SBNode("SB-24", "Hidden Assumption Attacker", 3, "Attack hidden assumptions"),
    SBNode("SB-25", "Framing Challenger", 3, "Challenge the current framing"),
    SBNode("SB-26", "Courage Wall", 3, "Force naming what is being avoided"),
    SBNode("SB-27", "Identity Resistance Check", 3, "Check identity-level resistance"),
    SBNode("SB-28", "Verified Truth Lock", 3, "Lock verified truth elements"),
    # Stage 4 — Evidence & Validation
    SBNode("SB-29", "Evidence Ledger", 4, "Build proof levels"),
    SBNode("SB-30", "Source Tagger", 4, "Tag REAL_TOOL / MANUAL / MEMORY / SIMULATED"),
    SBNode("SB-31", "Domain-Adaptive Auditor", 4, "Different validation rules per domain"),
    SBNode("SB-32", "Literature & Historical Pattern Hunter", 4, "Search patterns across time/domains, holy books, research"),
    SBNode("SB-33", "Live Real-World Data Link", 4, "Connect to live real-world data"),
    SBNode("SB-34", "Proof Ladder Builder", 4, "Build the proof ladder"),
    SBNode("SB-35", "In-Silico Validator", 4, "Run in-silico validation where needed"),
    SBNode("SB-36", "Evidence Completion", 4, "Complete evidence status before connection work"),
    # Stage 5 — Connection, Dot & Memory
    SBNode("SB-37", "Dot Connection Engine", 5, "Search across all prior SB points for connections"),
    SBNode("SB-38", "Cross-Domain Fusion", 5, "Force fusion between domains, check force-fit risk"),
    SBNode("SB-39", "Non-Text Pattern Detector", 5, "Patterns in images, watermarks, footprints"),
    SBNode("SB-40", "Merge Proposal", 5, "Propose merges when real value exists"),
    SBNode("SB-41", "Convergence Hunter", 5, "Hunt similar conclusions from different paths"),
    SBNode("SB-42", "Cross-Point Contradiction", 5, "Find contradictions across points"),
    SBNode("SB-43", "New Parameter Generator", 5, "Generate new parameters when data does not fit"),
    SBNode("SB-44", "Memory Sync", 5, "Update and sync memory"),
    # Stage 6 — Synthetic, Invention & New Parameters
    SBNode("SB-45", "Synthetic Fuel Injector", 6, "Hypothetical/Counterfactual/Heuristic Fiction/Working Fiction/Apostatic Inversion"),
    SBNode("SB-46", "Invention Seed Protector", 6, "Protect early invention seeds from forced resolution"),
    SBNode("SB-47", "Working Fiction Scaffold", 6, "Build working-fiction scaffolds"),
    SBNode("SB-48", "Apostatic Inversion", 6, "See it from the exact opposite / enemy's eyes"),
    SBNode("SB-49", "Heuristic Simplification", 6, "Apply heuristic simplification"),
    SBNode("SB-50", "Synthetic Tagging", 6, "Heavy [SYNTHETIC] tagging with proof debt + expiry"),
    SBNode("SB-51", "Parameter Labeler", 6, "Generate and label new parameters"),
    SBNode("SB-52", "Synthetic Completion", 6, "Complete synthetic handling with review rules"),
    # Stage 7 — Risk, Ethics & Human Control
    SBNode("SB-53", "Risk & Command Gate", 7, "Legal/ethical/harmful/high-stakes risk check; force human review"),
    SBNode("SB-54", "Critical Logic Wall", 7, "Detect Data/Logic/Frame/Complexity/Motive/Moral/Identity/Time stalls"),
    SBNode("SB-55", "High-Risk Merge Review", 7, "Force human review on high-synthetic / high-risk merges"),
    SBNode("SB-56", "Override Ledger", 7, "Record every human decision with reason"),
    SBNode("SB-57", "Non-Resolution Protector", 7, "Protect valid non-resolution states"),
    SBNode("SB-58", "Reality Re-Anchor", 7, "Check conclusion against original raw source / Point Zero"),
    SBNode("SB-59", "Embodied Check", 7, "Body/intuition resistance treated as valid data"),
    SBNode("SB-60", "Final Decision Prep", 7, "Prepare everything for final human decision"),
    # Stage 8 — Output, Memory Update & Brain Maintenance
    SBNode("SB-61", "Master Log Update", 8, "Record every parameter, source, merger, parked info"),
    SBNode("SB-62", "Weekly Brain Update Trigger", 8, "Trigger weekly local brain updates (Mondays)"),
    SBNode("SB-63", "Memory Sync (All Points)", 8, "Sync memory across all points"),
    SBNode("SB-64", "Final Output Generator", 8, "Generate the final deliverable"),
    SBNode("SB-65", "Feed-Forward Router", 8, "Send everything back to any point for re-merging"),
    SBNode("SB-66", "Full Compilation", 8, "Compile all outputs"),
    SBNode("SB-67", "Breakthrough Lock", 8, "Score and lock breakthrough moments"),
    SBNode("SB-68", "Human Halt Gate", 8, "Human has full halt authority"),
    SBNode("SB-69", "Long-Term Memory Lock", 8, "Lock important findings into long-term memory"),
    SBNode("SB-70", "Run Completion", 8, "Complete the run, prepare for reset or new work"),
)

# The 25 URR verification points (5 blocks of 5).
URR_NODES: tuple[URRNode, ...] = (
    URRNode("URR-01", "Raw Source Integrity", "After Stage 1-2"),
    URRNode("URR-02", "Human Layer Check", "After Stage 1-2"),
    URRNode("URR-03", "Truth Pressure Review", "After Stage 1-2"),
    URRNode("URR-04", "Intent Gate Review", "After Stage 1-2"),
    URRNode("URR-05", "Early Classification Audit", "After Stage 1-2"),
    URRNode("URR-06", "Evidence Quality Audit", "After Stage 4-5"),
    URRNode("URR-07", "Synthetic Tagging Audit", "After Stage 4-5"),
    URRNode("URR-08", "First Verification Gate", "After SB-08 (intake)"),
    URRNode("URR-09", "Merge Integrity Check", "After Stage 4-5"),
    URRNode("URR-10", "Force-Fit Risk Review", "After Stage 4-5"),
    URRNode("URR-11", "Risk Gate", "High synthetic or high risk"),
    URRNode("URR-12", "Ethics Gate", "High synthetic or high risk"),
    URRNode("URR-13", "Human Override Review", "High synthetic or high risk"),
    URRNode("URR-14", "Synthetic Cage Review", "High synthetic or high risk"),
    URRNode("URR-15", "Reality Anchor Review", "High synthetic or high risk"),
    URRNode("URR-16", "Memory Accuracy Audit", "After major merges"),
    URRNode("URR-17", "New Parameter Audit", "After major merges"),
    URRNode("URR-18", "Cross-Point Audit", "After major merges"),
    URRNode("URR-19", "Master Log Audit", "After major merges"),
    URRNode("URR-20", "Drift Detection", "After major merges"),
    URRNode("URR-21", "Full Run Integrity", "End of major runs"),
    URRNode("URR-22", "Public-Safe Boundary Check", "End of major runs"),
    URRNode("URR-23", "Falsifier Presence Check", "End of major runs"),
    URRNode("URR-24", "Human Final Gate", "End of major runs"),
    URRNode("URR-25", "Archive & Closure", "End of major runs"),
)

# Pyramid level template for every node (Node -> Main -> Sub -> Micro).
SB_PYRAMID = {"node": 1, "main": (5, 10), "sub": (10, 20), "micro": (20, 30)}
URR_PYRAMID = {"node": 5, "main": (10, 15)}

MAX_SB_NODES = 100   # scalable beyond 70
MAX_URR_NODES = 40   # scalable beyond 25


def sb_by_stage(stage: int) -> list[SBNode]:
    return [n for n in SB_NODES if n.stage == stage]


def sb_by_id(sb_id: str) -> SBNode | None:
    return next((n for n in SB_NODES if n.sb_id == sb_id), None)
