"""Sourceborn (SBUR) — a private, continuously-learning reasoning engine.

A control layer around a base model that thinks by *example and archetype*
(eternal example, present fact), runs the SB + URR pipeline over a pyramid of
local brains, clones the user's voice, and gets wiser with every use.

Quick start::

    from sourceborn import SourcebornEngine
    eng = SourcebornEngine(root=".sourceborn")
    result = eng.run("should I scale my small business or do an MBA?")
    print(result.output.answer)
"""

from .engine import SourcebornEngine, RunResult
from .memory import Memory, NodeBrain
from .persona import Persona
from .wisdom import WisdomBank
from .models import RawSource, PointZero, MemoryEntry, Output
from .enums import (
    HaltType, LoopType, LoopStatus, Classification, EvidenceTag,
    ForceFitRisk, ConstructionMode, PenetrationScore, Lane,
)

__version__ = "0.1.0"

__all__ = [
    "SourcebornEngine", "RunResult", "Memory", "NodeBrain", "Persona",
    "WisdomBank", "RawSource", "PointZero", "MemoryEntry", "Output",
    "HaltType", "LoopType", "LoopStatus", "Classification", "EvidenceTag",
    "ForceFitRisk", "ConstructionMode", "PenetrationScore", "Lane",
]
