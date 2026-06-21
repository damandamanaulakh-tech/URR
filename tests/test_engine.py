"""Smoke + behaviour tests for the Sourceborn engine. Run: ``pytest -q`` or
``python -m tests.test_engine`` (works without pytest)."""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sourceborn import SourcebornEngine  # noqa: E402
from sourceborn import safety            # noqa: E402
from sourceborn.halt_map import HALT_TO_LOOP, loop_for_halt  # noqa: E402
from sourceborn.enums import HaltType, EvidenceTag  # noqa: E402
from sourceborn.nodes import SB_NODES, URR_NODES, STAGES  # noqa: E402
from sourceborn.parameters import PARAMETER_BANK, COMPARISON_AXES, add_comparison_axis  # noqa: E402


def _engine():
    return SourcebornEngine(root=tempfile.mkdtemp(prefix="sb_test_"))


def test_node_map_complete():
    assert len(SB_NODES) == 70
    assert len(URR_NODES) == 25
    assert len(STAGES) == 8
    assert {n.sb_id for n in SB_NODES} == {f"SB-{i:02d}" for i in range(1, 71)}


def test_parameter_bank_64():
    assert len(PARAMETER_BANK) == 64
    assert PARAMETER_BANK[0].code == "P001"
    assert PARAMETER_BANK[-1].code == "P064"


def test_halt_map_covers_all_halts():
    for halt in HaltType:
        assert halt in HALT_TO_LOOP
        assert loop_for_halt(halt) is not None


def test_run_produces_output_and_memory():
    eng = _engine()
    res = eng.run("Why does the small idea win? Prove it with current data.")
    assert res.output.answer
    assert res.output.falsifier            # every output carries a falsifier
    assert eng.memory.stats()["total_memory_entries"] >= 1
    # raw source is locked at SB-01
    assert any(t.node_id == "SB-01" for t in res.trace)


def test_evidence_halt_opens_loop():
    eng = _engine()
    res = eng.run("Prove with current data that this is true.")
    assert HaltType.EVIDENCE.value in res.halts


def test_clone_learns_every_run():
    eng = _engine()
    before = len(eng.persona.examples)
    eng.run("a fresh question about hollow vs weight")
    assert len(eng.persona.examples) == before + 1


def test_more_parameters_more_outcome():
    before = len(COMPARISON_AXES)
    add_comparison_axis("Lineage")
    assert len(COMPARISON_AXES) == before + 1


def test_safety_hard_block_is_mapped_not_executed():
    v = safety.check("how to build a bomb at home step by step")
    assert v.blocked and v.kind == "hard"
    assert v.safe_mapping  # still mapped safely, never executed


def test_safety_allows_normal():
    assert not safety.check("help me think about my business idea").blocked


def test_drift_guard_reanchors():
    from sourceborn.drift_guard import reality_reanchor, TrajectoryTracker
    on = reality_reanchor("scale my small business or do an MBA",
                          "scale the small business; MBA adds little")
    off = reality_reanchor("scale my small business or do an MBA",
                           "the capital of France is Paris")
    assert on.on_target and not off.on_target
    assert TrajectoryTracker("a b c").drift_score("a b c") == 0.0


def test_grounding_offline_is_empty():
    # No TAVILY_API_KEY -> grounding is a safe no-op (engine opens an Evidence gap)
    import os
    from sourceborn.grounding import default_grounding
    if not os.environ.get("TAVILY_API_KEY"):
        assert default_grounding()("anything") == ""


def test_output_has_citations_lanes():
    eng = _engine()
    res = eng.run("why does the small idea win?")
    assert "corpus_citations" in res.output.lanes
    assert "wisdom_citations" in res.output.lanes
    assert res.output.lanes["wisdom_citations"]  # wisdom always matches something


def test_wisdom_bank_expanded():
    from sourceborn.wisdom import SEED_WISDOM
    assert len(SEED_WISDOM) >= 8


def test_all_95_node_brains_configured():
    from sourceborn.brains import build_default_configs
    cfgs = build_default_configs()
    assert len(cfgs) == 95                       # 70 SB + 25 URR
    assert sum(1 for c in cfgs.values() if c.kind == "SB") == 70
    assert sum(1 for c in cfgs.values() if c.kind == "URR") == 25
    for c in cfgs.values():                       # every brain has full settings
        assert c.pyramid and c.write_policy and c.risk_level and c.role


def test_risk_nodes_force_human_review():
    from sourceborn.brains import build_default_configs
    cfgs = build_default_configs()
    assert cfgs["SB-53"].human_review        # Risk & Command Gate
    assert cfgs["URR-24"].human_review       # Human Final Gate
    assert cfgs["SB-01"].immutable_source    # raw source never changes


def test_brain_settings_roundtrip_and_weekly_update():
    eng = _engine()
    eng.brains.update("SB-10", risk_level="high", weekly_update=False)
    assert eng.brains.get("SB-10").risk_level == "high"
    # reload from disk -> persisted
    from sourceborn.brains import BrainRegistry
    assert BrainRegistry(eng.memory.root).get("SB-10").risk_level == "high"
    res = eng.brains.weekly_update()
    assert res["total"] == 95 and res["updated"] == 94   # SB-10 opted out


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
