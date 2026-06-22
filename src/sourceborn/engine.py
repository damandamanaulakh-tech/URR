"""SourcebornEngine — the control layer that binds the three memories.

It runs the SOURCEBORN operating flow (PRINCIPLE §IV) over the SB+URR node map:

    read & protect -> analyse true ask -> decompose -> bigger-picture triage
    -> example & wisdom match -> live grounding -> URR verify -> place -> deliver

The three memories it binds:
  * reflex  = the user's fed corpus + example bank (``Persona`` + ``Memory``)
  * instinct= the wisdom bank (``WisdomBank``)
  * eyes    = live fact (``grounding`` hook; pluggable)

Everything is written to the pyramid brains + Master Log, and every run teaches
the clone one more example (it gets wiser with use).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import safety
from .brains import BrainRegistry
from .core_gate import six_lenses
from .doubt import doubt_engine, falsifier as make_falsifier, witness
from .dots import dot_connections, merge_proposal
from .drift_guard import reality_reanchor
from .evidence import build_ledger, ladder_confidence
from .fuel import diagnose_stall, inject as inject_fuel
from .grounding import default_grounding
from .enums import (
    Classification, EvidenceTag, ForceFitRisk, HaltType, LoopType, PenetrationScore,
)
from .halt_map import loop_for_halt
from .llm import BaseModel, default_model
from .memory import Memory
from .models import (
    GapItem, MemoryEntry, Output, PointZero, ProofItem, RawSource, TraceEntry, URRPacket,
)
from .nodes import SB_NODES, URR_NODES, sb_by_id
from .parameters import COMPARISON_AXES, PARAMETER_BANK
from .persona import Persona
from .wisdom import WisdomBank


@dataclass
class RunResult:
    output: Output
    micro_questions: list[str]
    matched_examples: list[str]
    trace: list[TraceEntry]
    gaps: list[GapItem]
    proofs: list[ProofItem]
    halts: list[str]


class SourcebornEngine:
    def __init__(
        self,
        root: str = ".sourceborn",
        model: BaseModel | None = None,
        grounding: Callable[[str], str] | None = None,
    ) -> None:
        self.memory = Memory(root)
        self.brains = BrainRegistry(root)   # settings of all 70 SB + 25 URR brains
        self.persona = Persona(root)
        self.wisdom = WisdomBank(root)
        self.model = model or default_model()
        # live-fact hook (the "eyes"): Tavily if TAVILY_API_KEY set, else no-op.
        self.grounding = grounding or default_grounding()
        self.trace: list[TraceEntry] = []

    # -- helpers -----------------------------------------------------------
    def _t(self, node_id: str, action: str, status: str = "running",
           halt: str | None = None, note: str = "") -> None:
        self.trace.append(TraceEntry(node_id, action, status, halt, note))

    @staticmethod
    def _decompose(text: str) -> list[str]:
        """Split a messy ask into micro-questions/claims (PRINCIPLE step 3)."""
        import re
        parts = re.split(r"(?<=[.?!;])\s+|\n+|\band\b|\bthen\b", text.strip())
        return [p.strip(" -•\t") for p in parts if len(p.strip()) > 3] or [text.strip()]

    @staticmethod
    def _noise_strip(text: str) -> dict[str, list[str]]:
        """SB-02: separate the raw ask into channels (kept, never discarded)."""
        buckets: dict[str, list[str]] = {
            "fact": [], "feeling": [], "assumption": [], "pressure": [],
            "claim": [], "mystery": [], "invention_seed": [], "command": [],
        }
        for line in SourcebornEngine._decompose(text):
            low = line.lower()
            if any(w in low for w in ("i feel", "thrill", "fear", "ego", "pain", "love")):
                buckets["feeling"].append(line)
            elif any(w in low for w in ("must", "need", "want", "should", "have to")):
                buckets["command"].append(line)
            elif any(w in low for w in ("maybe", "what if", "could", "consider")):
                buckets["assumption"].append(line)
            elif any(w in low for w in ("invent", "new tool", "build", "create")):
                buckets["invention_seed"].append(line)
            elif any(w in low for w in ("why", "mystery", "unknown", "how come")):
                buckets["mystery"].append(line)
            else:
                buckets["claim"].append(line)
        return {k: v for k, v in buckets.items() if v}

    # -- URR micro-pass ----------------------------------------------------
    def urr_micropass(self, urr_id: str, sb_node_id: str, content: str,
                      synthetic: bool = False) -> URRPacket:
        """A verification gate: classify, score force-fit, detect halts.

        This is the rule-based URR. A model-backed URR can subclass / replace it.
        """
        low = content.lower()
        classification = Classification.CLAIM.value
        evidence = EvidenceTag.REVIEW.value
        force_fit = ForceFitRisk.LOW.value
        halt: str | None = None

        if synthetic:
            classification = Classification.SPECULATION.value
            evidence = EvidenceTag.SYNTHETIC.value
        if any(w in low for w in ("always", "everyone", "never", "guaranteed", "obviously")):
            force_fit = ForceFitRisk.HIGH.value
            halt = HaltType.LOGIC.value
        if any(w in low for w in ("proof", "evidence", "data", "fact", "current")):
            if not self.grounding(content):
                halt = HaltType.EVIDENCE.value
        verdict = safety.check(content)
        risk_flags: list[str] = []
        if verdict.blocked:
            halt = HaltType.SAFETY.value
            risk_flags = verdict.reasons

        return URRPacket(
            urr_id=urr_id, sb_node_id=sb_node_id, classification=classification,
            evidence_tag=evidence, force_fit_risk=force_fit,
            halt_triggered=halt is not None, halt_type=halt, risk_flags=risk_flags,
            recommended_action="open_loop" if halt else "proceed",
            trace_note=f"URR {urr_id} on {sb_node_id}",
        )

    # -- the run -----------------------------------------------------------
    def run(self, raw_text: str, origin: str = "chat", public_safe: bool = False,
            learn: bool = True, model: BaseModel | None = None) -> RunResult:
        active_model = model or self.model
        self.trace = []
        gaps: list[GapItem] = []
        proofs: list[ProofItem] = []
        halts: list[str] = []

        # 0. SAFETY (hard boundary, mapped not executed) ------------------
        verdict = safety.check(raw_text)
        if verdict.blocked:
            self._t("SB-53", "risk_gate", "held", HaltType.SAFETY.value,
                    "; ".join(verdict.reasons))

        # 1. READ & PROTECT — SB-01 Point Zero Lock, SB-04 preserve --------
        raw = RawSource(text=raw_text, origin=origin).lock()
        self.memory.write("SB-01", MemoryEntry(
            node_id="SB-01", raw_source_id=raw.raw_source_id, content=raw_text,
            classification=Classification.REVIEW_ONLY.value,
            evidence_tag=EvidenceTag.OPEN.value, tags=["raw_source", "locked"],
        ), name="Point Zero Lock")
        pz = PointZero(raw_source_id=raw.raw_source_id, literal_ask=raw_text[:200])
        pz.locked = True
        self._t("SB-01", "point_zero_lock", "running", note="raw source locked")

        # 2. NOISE STRIP — SB-02 ------------------------------------------
        channels = self._noise_strip(raw_text)
        self.memory.write("SB-02", MemoryEntry(
            node_id="SB-02", raw_source_id=raw.raw_source_id,
            content="noise-stripped channels", parameters={"channels": channels},
            pyramid={"main": list(channels.keys()), "sub": [], "micro": []},
        ), name="Noise & Static Stripper")
        self._t("SB-02", "noise_strip", "running", note=",".join(channels))

        # 3. DECOMPOSE into micro-questions -------------------------------
        micro = self._decompose(raw_text)
        self._t("SB-02", "decompose", "running", note=f"{len(micro)} micro-questions")

        # 4. TRIAGE routine vs deep ---------------------------------------
        deep = len(micro) > 1 or any(
            w in raw_text.lower() for w in ("why", "prove", "mystery", "invent", "rh", "theory")
        )
        self._t("SB-03", "triage", "running", note="deep" if deep else "routine")

        # 4b. CORE GATE — six lenses (SB-10): read the human under the words
        core = six_lenses(raw_text)
        self.memory.write("SB-10", MemoryEntry(
            node_id="SB-10", raw_source_id=raw.raw_source_id,
            content=f"core gate dominant lens: {core['dominant_lens']}",
            parameters={"lenses": core["lenses"]},
            pyramid={"main": [k for k, v in core["lenses"].items() if v["active"]],
                     "sub": [], "micro": []},
            tags=["core_gate", "human_layer"],
        ), name="Core Gate — Six Lenses")
        self._t("SB-10", "core_gate", "running",
                note=f"dominant: {core['dominant_lens']} ({core['active_count']}/6 lenses)")

        # 5. EXAMPLE & WISDOM MATCH (the heart) ---------------------------
        matched: list[str] = []
        seen: set[str] = set()
        per_part_refs: list[list[str]] = []
        for mq in micro:
            refs: list[str] = []
            for ex in self.persona.recall(mq):            # reflex (your corpus)
                refs.append(ex.question[:60])
                item = f"corpus: {ex.question[:60]}"
                if item not in seen:
                    seen.add(item); matched.append(item)
            for score, w, axes in self.wisdom.match(mq):  # instinct (wisdom)
                item = f"{w.source}: {w.pattern[:70]} [axes: {', '.join(axes) or '—'}]"
                if item not in seen:
                    seen.add(item); matched.append(item)
            per_part_refs.append(refs)
        self.memory.write("SB-32", MemoryEntry(
            node_id="SB-32", raw_source_id=raw.raw_source_id,
            content="example & wisdom match", parameters={"matched": matched},
            tags=["example_match"],
        ), name="Literature & Historical Pattern Hunter")
        self._t("SB-32", "example_wisdom_match", "running", note=f"{len(matched)} matches")

        # 5b. DOT CONNECTION + MERGE (SB-37/40): sources recurring across parts
        connections = dot_connections(per_part_refs)
        merge = merge_proposal(connections)
        if connections:
            self._t("SB-37", "dot_connection", "running",
                    note=f"{len(connections)} cross-links")
        if merge:
            self.memory.master_log({"event": "merge_proposal",
                                    "contributing": merge["contributing"]})
            self._t("SB-40", "merge_proposal", "held", note="needs human gate")

        # 6. LIVE GROUNDING — SB-33 (pluggable eyes) ----------------------
        live = self.grounding(raw_text)
        if not live and deep:
            gaps.append(GapItem("No live fact source connected", "Evidence", "Medium",
                                LoopType.EVIDENCE.value))
        self._t("SB-33", "live_grounding", "running" if live else "gap_open",
                note="live data" if live else "no live source")

        # Stage 4 — Evidence ladder + source tags (SB-29)
        corpus_refs = [m[8:] for m in matched if m.startswith("corpus:")]
        ledger = build_ledger(micro, bool(live), corpus_refs)
        ladder_conf = ladder_confidence(ledger)
        self._t("SB-29", "evidence_ledger", "running",
                note=f"ladder confidence {ladder_conf}")

        # 7. URR VERIFY ----------------------------------------------------
        packet = self.urr_micropass("URR-08", "SB-08", raw_text)
        if packet.halt_triggered:
            halts.append(packet.halt_type or "")
            loop = loop_for_halt(HaltType(packet.halt_type))
            self.memory.master_log({"event": "halt", "type": packet.halt_type,
                                    "new_loop": loop.value})
            self._t("URR-08", "verify", "held", packet.halt_type,
                    f"opened {loop.value}")
            if packet.halt_type == HaltType.EVIDENCE.value:
                gaps.append(GapItem("Evidence halt at URR-08", "Evidence", "High",
                                    loop.value))
        else:
            self._t("URR-08", "verify", "passed", note=packet.classification)

        # 8. PLACE — build the lanes (URR-07 output lanes) ----------------
        draft = active_model.complete(
            system=self.persona.voice_guidance(),
            prompt=f"Answer this using the matched examples and live fact.\n"
                   f"ASK: {raw_text}\nMATCHED: {matched}\nLIVE: {live or 'none'}",
        )

        # Stage 3 — Doubt Engine + Witness (SB-20/22): attack before delivery
        doubt = doubt_engine(draft, bool(live), len(matched))
        blind = witness([t.node_id for t in self.trace],
                        core["dominant_lens"], bool(live))
        self._t("SB-20", "doubt_engine", "held" if doubt["bites"] else "passed",
                note=doubt["verdict"])
        self._t("SB-22", "witness", "running", note=blind[0])

        # Stage 6 — Synthetic Fuel if stalled (SB-45): force motion, never fake fact
        stall = diagnose_stall(halts, bool(live), len(matched), doubt["bites"])
        fuel_item = inject_fuel(stall, raw_text) if stall else None
        if fuel_item:
            self._t("SB-45", "synthetic_fuel", "synthetic_assumption_active",
                    note=fuel_item["fuel"])

        # Stage 7 — Embodied Check (SB-59) + Non-Resolution Protector (SB-57)
        embodied_ok = not (doubt["bites"] or (bool(halts) and not live))
        self._t("SB-59", "embodied_check", "passed" if embodied_ok else "held",
                note="sits right" if embodied_ok else "resistance — re-loop")
        non_resolution = bool(halts) and not live and doubt["bites"]
        if non_resolution:                     # Principle 2: holding is valid
            self._t("SB-57", "non_resolution_protector", "running",
                    note="valid hold / incubate — do not force a product")

        lanes = {
            "reality_path": {"known": live or "needs live source",
                             "what_would_prove_it": "live web grounding (Tavily)"},
            "wild_path": {"preserved": channels.get("invention_seed", []) +
                          channels.get("mystery", [])},
            "classification": packet.classification,
            "sequence_path": [n.sb_id for n in SB_NODES[:8]],
            # citations — every claim is backed below it (the grounding pyramid)
            "corpus_citations": [m[8:] for m in matched if m.startswith("corpus:")][:5],
            "wisdom_citations": [m for m in matched if not m.startswith("corpus:")][:5],
            # Core Gate reading (the human under the words)
            "human_layer": {"dominant_lens": core["dominant_lens"],
                            "active": {k: v["reading"] for k, v in
                                       core["lenses"].items() if v["active"]}},
            # Stage 3-6 depth
            "evidence_ledger": ledger,
            "connections": connections,
            "merge_proposal": merge,
            "doubt": doubt,
            "witness": blind,
            "synthetic_fuel": fuel_item,
            "embodied_check": "sits right" if embodied_ok else "resistance — re-loop",
            "non_resolution": non_resolution,
        }
        if verdict.blocked:
            lanes["safety"] = verdict.safe_mapping

        # 8b. REALITY RE-ANCHOR — anti-divert (SB-58): did we drift from Point Zero?
        anchor = reality_reanchor(pz.literal_ask, draft)
        lanes["reality_reanchor"] = anchor.note
        self._t("SB-58", "reality_reanchor",
                "passed" if anchor.on_target else "held", note=anchor.note)

        # 9. DELIVER -------------------------------------------------------
        out = Output(
            answer=draft,
            lanes=lanes,
            evidence_tag=packet.evidence_tag,
            classification=(Classification.REVIEW_ONLY.value if non_resolution
                            else packet.classification),
            confidence="Low" if (doubt["bites"] or gaps or halts) else ladder_conf,
            falsifier=make_falsifier(raw_text),
            penetration_score=(PenetrationScore.PENETRATED.value if deep
                               else PenetrationScore.SHALLOW.value),
            open_question=("Held — non-resolution is valid here; needs evidence or "
                           "incubation (Principle 2)." if non_resolution
                           else (channels.get("mystery", [""])[0]
                                 if "mystery" in channels else "")),
            public_safe=public_safe,
            matched_examples=matched,
        )
        self.memory.write("SB-64", MemoryEntry(
            node_id="SB-64", raw_source_id=raw.raw_source_id, content=out.answer,
            classification=out.classification, evidence_tag=out.evidence_tag,
            parameters={"penetration": out.penetration_score, "confidence": out.confidence},
            tags=["final_output"],
        ), name="Final Output Generator")
        self._t("SB-64", "deliver", "passed", note=out.evidence_tag)

        # COMPOUND: the clone learns one more example (gets wiser with use) -
        if learn:
            self.persona.learn(raw_text, out.answer, note="auto-learned from run",
                               classification=out.classification)
            self._t("SB-69", "long_term_memory_lock", "passed",
                    note="example bank +1")

        return RunResult(out, micro, matched, list(self.trace), gaps, proofs, halts)

    # -- RGL: Recursive Genesis Loop ---------------------------------------
    def run_recursive(self, raw_text: str, loops: int = 3,
                      model: BaseModel | None = None, converge: float = 0.30) -> dict:
        """The RGL (RGL.txt): the loop's shape is invariant, the content
        compounds. Each pass's Point Zero carries the previous pass's product;
        it re-opens up to ``loops`` times, stopping early when the product stops
        changing (convergence). Only the final pass teaches the clone.
        """
        history: list[dict] = []
        product = ""
        last: RunResult | None = None
        converged = False
        n = max(1, loops)
        for i in range(n):
            text = raw_text if not product else (
                f"{raw_text}\n\n[carry-forward from loop {i}] {product[:400]}")
            last = self.run(text, learn=(i == n - 1), model=model)
            history.append({
                "loop": i + 1, "answer": last.output.answer,
                "confidence": last.output.confidence,
                "penetration": last.output.penetration_score,
            })
            if product:
                drift = reality_reanchor(product, last.output.answer).drift_score
                if drift < converge:
                    converged = True
                    product = last.output.answer
                    break
            product = last.output.answer
        return {"result": last, "recursion": {
            "loop_count": len(history), "converged": converged, "history": history}}
