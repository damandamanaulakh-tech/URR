"""CLI: ``python -m sourceborn "your question"``  (add --public for public-safe).

With no question, runs the demo.
"""

from __future__ import annotations

import sys

from .engine import SourcebornEngine


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        from .demo import main as demo_main
        demo_main()
        return 0

    public = "--public" in argv
    argv = [a for a in argv if a != "--public"]
    ask = " ".join(argv)

    eng = SourcebornEngine(root=".sourceborn")
    result = eng.run(ask, public_safe=public)
    o = result.output

    print("\n--- SOURCEBORN ---")
    print(f"ask          : {ask}")
    print(f"answer       : {o.answer}")
    print(f"classification: {o.classification} | evidence: {o.evidence_tag} "
          f"| confidence: {o.confidence} | penetration: {o.penetration_score}")
    if result.matched_examples:
        print("matched examples:")
        for m in result.matched_examples:
            print(f"  • {m}")
    if result.halts:
        print(f"halts -> loops: {result.halts}")
    print(f"falsifier    : {o.falsifier}")
    print(f"memory       : {eng.memory.stats()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
