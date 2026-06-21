"""Runnable end-to-end demo of the Sourceborn brain (offline, no API key).

    python -m sourceborn.demo

Shows: raw-source lock, noise strip, decompose, triage, example+wisdom match,
URR verify with halt->loop, the URR-07 output lanes, the grounding pyramid, the
clone learning a new example, and the pyramid-brain memory growing on disk.
"""

from __future__ import annotations

import tempfile

from .engine import SourcebornEngine


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> None:
    root = tempfile.mkdtemp(prefix="sourceborn_demo_")
    eng = SourcebornEngine(root=root)

    banner("SOURCEBORN — offline demo")
    print(f"brain root: {root}")
    print(f"base model: {eng.model.__class__.__name__} "
          f"(set ANTHROPIC_API_KEY to use Claude)")

    # Seed a couple of the user's own examples (the clone's muscle memory).
    eng.persona.learn(
        "is a small business with one clear idea better than scaling via MBA?",
        "Start from the idea + revenue + flaw-finding, not MBA scaling bias. "
        "Hollow can beat weight. Keep the wild path; classify, don't reject.",
        note="seed example",
    )

    ask = ("They say everyone fails in business without an MBA. "
           "I feel a thrill to build a new tool. Why does the small idea win? "
           "Prove it with current data.")
    banner("ASK")
    print(ask)

    result = eng.run(ask)

    banner("MICRO-QUESTIONS (decompose)")
    for i, mq in enumerate(result.micro_questions, 1):
        print(f"  {i}. {mq}")

    banner("EXAMPLE & WISDOM MATCH (eternal example)")
    for m in result.matched_examples:
        print(f"  • {m}")

    banner("URR VERIFY / HALTS -> LOOPS")
    print(f"  halts: {result.halts or 'none'}")
    for g in result.gaps:
        print(f"  gap: {g.description} -> {g.suggested_loop}")

    banner("OUTPUT LANES (URR-07)")
    o = result.output
    for k, v in o.lanes.items():
        print(f"  [{k}] {v}")
    print(f"\n  classification : {o.classification}")
    print(f"  evidence tag   : {o.evidence_tag}")
    print(f"  confidence     : {o.confidence}")
    print(f"  penetration    : {o.penetration_score}")
    print(f"  falsifier      : {o.falsifier}")
    print(f"  answer         : {o.answer}")

    banner("GROUNDING PYRAMID")
    print("  DELIVERED ANSWER")
    print("    ^ backed by LIVE FACT (web/today)")
    print("    ^ backed by WISDOM / ARCHETYPE (holy books, proverbs)")
    print("    ^ backed by YOUR CORES / EXAMPLE BANK (muscle memory)")
    print("    ^ backed by RAW SOURCE (locked at Point Zero)")

    banner("TRACE (SB/URR nodes fired)")
    for t in result.trace:
        flag = f" [HALT:{t.halt}]" if t.halt else ""
        print(f"  {t.node_id:7} {t.action:24} {t.status:8}{flag}  {t.note}")

    banner("PYRAMID-BRAIN MEMORY (on disk)")
    print(f"  {eng.memory.stats()}")
    print(f"  persona example bank: {len(eng.persona.examples)} examples")
    print(f"  (every run teaches the clone one more example -> it gets wiser)")


if __name__ == "__main__":
    main()
