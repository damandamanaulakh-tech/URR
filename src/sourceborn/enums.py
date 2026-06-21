"""Controlled vocabularies for the Sourceborn (SBUR) engine.

Every label the engine can attach to anything lives here, so that the rest of
the code never invents an ad-hoc string. The values are taken directly from the
canonical cores (URR-07, SBUR Full Engine Spec, SB Master Core, ARD 3.1).
"""

from __future__ import annotations

from enum import Enum


class HaltType(str, Enum):
    """A Halt is never a failure. Each type maps to a loop in ``halt_map``."""

    EVIDENCE = "Evidence"
    LANGUAGE = "Language"
    LOGIC = "Logic"
    PRODUCT = "Product"
    MYSTERY = "Mystery"
    STATUS = "Status"
    SAFETY = "Safety"
    PUBLIC_CLAIM = "Public Claim"
    REALITY = "Reality"
    CONTRADICTION = "Contradiction"


class LoopType(str, Enum):
    """The 30 canonical loop types plus the RGL sub-loops and a few extensions
    found across the cores (Sleep, Reverse, Triage, Stall Diagnostic, ...)."""

    # --- The 30 canonical SB loops -------------------------------------
    ROOT_ASK = "Root Ask Loop"
    SOURCE = "Source Loop"
    SEQUENCE = "Sequence Loop"
    PATTERN = "Pattern Loop"
    INTENT_CONDITION_POWER = "Intent/Condition/Power Loop"
    DOMAIN_ROUTE = "Domain Route Loop"
    EVIDENCE = "Evidence Loop"
    REALITY_CHECK = "Reality Check Loop"
    WILD_PATH = "Wild Path Loop"
    MYSTERY = "Mystery Loop"
    INVENTION = "Invention Loop"
    CONTRADICTION = "Contradiction Loop"
    FALSIFIER = "Falsifier Loop"
    SYNTHETIC_FUEL = "Synthetic Fuel Loop"
    FICTION_AUDIT = "Fiction Audit Loop"
    DISCARD = "Discard Loop"
    HALT = "Halt Loop"
    PRODUCT_ROUTE = "Product Route Loop"
    REVIEW_VERIFICATION = "Review/Verification Loop"
    POINT_ZERO_WITH_PRODUCT = "Point Zero with Product Loop"
    POINT_ZERO_PLUS_PRODUCT = "Point Zero + Product Loop"
    PUBLIC_EXTRACTION = "Public Extraction Loop"
    CODING = "Coding Loop"
    FILE_EXTRACTION = "File Extraction Loop"
    REPORT = "Report Loop"
    PPT = "PPT Loop"
    MEDIA = "Media Loop"
    ADMIN_REVIEW = "Admin Review Loop"
    META_CORE_REVIEW = "Meta-Core Review Loop"
    CONTROLLED_RECURSIVE = "Controlled Recursive Loop"

    # --- RGL master sub-loops -----------------------------------------
    ORIGIN = "Origin Loop"
    RECOGNITION = "Recognition Loop"
    VALIDATION = "Validation Loop"
    GENERATION = "Generation Loop"
    RESOLUTION = "Resolution Loop"
    RETURN = "Return Loop"

    # --- Extensions seen across the cores ------------------------------
    SLEEP = "Sleep Loop"
    TIME_STALL = "Time-Stall Loop"
    REVERSE = "Reverse Loop"
    TRIAGE = "Triage Loop"
    STALL_DIAGNOSTIC = "Stall Diagnostic Loop"
    DRIFT_CONTROL = "Drift Control Loop"


class LoopStatus(str, Enum):
    """Shared status values across all loops (SB Master Core, section 3.2)."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    WAITING_FOR_EVIDENCE = "waiting_for_evidence"
    WAITING_FOR_USER = "waiting_for_user"
    SYNTHETIC_ASSUMPTION_ACTIVE = "synthetic_assumption_active"
    GAP_OPEN = "gap_open"
    HELD = "held"
    PROTECTED = "protected"
    SEPARATE = "separate"
    PASSED = "passed"
    VERIFIED = "verified"
    CLOSED = "closed"
    FAILED = "failed"


class Classification(str, Enum):
    """URR Classification Path labels. Nothing is rejected at intake; it is
    *classified* instead (URR-07, Lane 3)."""

    FACT = "Fact"
    CLAIM = "Claim"
    RUMOR = "Rumor"
    BELIEF = "Belief"
    SPECULATION = "Speculation"
    UNKNOWN = "Unknown"
    NEEDS_EVIDENCE = "Needs Evidence"
    CONTRADICTION = "Contradiction"
    PERSONAL_THEORY = "Personal Theory"
    BLOCKED_EXECUTION = "Blocked Execution"
    NOT_FOR_PUBLIC = "Not for Public Publish"
    PUBLIC_SAFE_CANDIDATE = "Public-Safe Extract Candidate"
    REVIEW_ONLY = "Review Only"
    HALT_POINT = "Halt Point"
    INVENTION_CANDIDATE = "Invention Candidate"
    PRODUCT_CANDIDATE = "Product Candidate"


class EvidenceTag(str, Enum):
    """Non-negotiable evidence tag carried by every output (ARD 3.1 Rule Lock).

    Exactly one of these must sit on any claim before it leaves the engine.
    """

    FACT = "FACT"          # Visible, externally supported
    REVIEW = "REVIEW"      # Plausible but not proven
    SYNTHETIC = "SYNTHETIC"  # Useful fiction only, until promoted by evidence
    RUMOR = "RUMOR"        # Not used as evidence; pressure-test only
    OPEN = "OPEN"          # Deliberately unresolved


class ForceFitRisk(str, Enum):
    """Risk that the engine is forcing a pattern that is not there.
    HIGH/CRITICAL holds the stage until resolved (SBUR spec, Stage 10)."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ConstructionMode(str, Enum):
    """Reading mode declared before interpretation (ARD 3.1 Node 17)."""

    ANALYTIC = "Analytic"
    SYMBOLIC = "Symbolic"
    EMOTIONAL = "Emotional"
    PRACTICAL = "Practical"
    MYTHIC = "Mythic"


class PenetrationScore(str, Enum):
    """How deep the engine actually went (ARD 3.1 output template)."""

    SURFACE = "Surface"
    SHALLOW = "Shallow"
    PENETRATED = "Penetrated"
    CORE_BREACH = "Core Breach"


class Lane(str, Enum):
    """The URR-07 output lanes."""

    REALITY = "Reality Path"
    WILD = "Wild Path / Personal Theory"
    CLASSIFICATION = "Classification Path"
    SEQUENCE = "Sourceborn Sequence Path"
    PROOF = "Proof Loop"
    CONTRADICTION = "Contradiction Loop"
    MYSTERY = "Mystery Loop"
    INVENTION = "Invention Loop"
    DATA_BANK = "Data Bank"
    PUBLIC_EXTRACTION = "Public Extraction Path"
    CARRY_FORWARD = "Carry-Forward Block"
