# Sourceborn (URR / SBUR)

A **private, continuously-learning reasoning engine** that thinks by *example and
archetype* — **"eternal example, present fact; more parameters, more outcome."**

It is a **control layer around a base model** (your Claude key), not a new trained
model. It clones your voice, runs the **SB + URR** pipeline over a **pyramid of
local brains** (70 SB + 25 URR nodes), and **gets wiser every time you use it**.

## The three memories
- **Reflex** — your fed corpus + example bank (*clone me*) → `persona.py`, `memory.py`
- **Instinct** — wisdom bank: holy books, proverbs, archetypes → `wisdom.py`
- **Eyes** — live fact (web/Tavily) → `engine.grounding` hook

## Try it (no install, no API key)
```bash
python -m sourceborn.demo                 # full offline walkthrough
python -m sourceborn "why does the small idea win? prove it"
PYTHONPATH=src python3 tests/test_engine.py   # 9 tests
```
Set `ANTHROPIC_API_KEY` to swap the offline stub for real Claude reasoning.

## Feed your brain (continuous learning)
```bash
python tools/docx2txt.py yourfile.docx > yourfile.txt   # convert docs first
python -c "import sys; sys.path.insert(0,'src'); from sourceborn.ingest import ingest_folder; print(ingest_folder('path/to/corpus'))"
```

## Layout
| Path | What |
|------|------|
| `docs/SOURCEBORN_CORE.md` | the canonical merged spec (single source of truth) |
| `docs/RECOMMENDATION.md` | how to build it (phased) + honest "unrestricted" note |
| `engine/sourceborn_system_prompt.md` | paste-anywhere engine prompt for any chat model |
| `src/sourceborn/` | the runnable engine (nodes, params, memory, persona, wisdom, URR) |
| `tests/` · `tools/` | tests · docx→txt helper |

Your private brain is written to `.sourceborn/` (git-ignored — never committed).

## Status
**Phase 1 (ownable core) is done and tested.** Phase 2 = wire your Claude key +
Tavily + build out the Wisdom Bank / Example-Match heart. Phase 3 = a private UI
(Lovable on top, or local). See `docs/RECOMMENDATION.md`.

Lineage: Raw Definition Engine → ARD / RGL → URR-07 → Secureborn → Sourceborn / SBUR
→ the 70-SB/25-URR "Omni" core. MIT licensed.
