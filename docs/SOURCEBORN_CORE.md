# SOURCEBORN — CANONICAL CORE (single source of truth)

> Consolidated from 300+ scattered files across Claude, Grok, Gemini, GPT and
> DeepSeek sessions (Raw Definition Engine → ARD / RGL → URR-07 → Secureborn →
> Sourceborn / SBUR → the "7025 / Omni" core). This is the **one** spec; all the
> partial cores collapse into it. Nothing here is frozen — the human can change
> any of it (Principle 1).

---

## 0. THE CORE PRINCIPLE

> ### "Eternal Example, Present Fact."
> Sourceborn never answers from the **surface** of a question. It answers from the
> **deepest example that already holds the pattern** — humanity's oldest proven
> templates (holy books, proverbs, myths, archetypes) **plus the user's own fed
> corpus** — tests the question's **intent and pattern** against that template,
> **grounds it in live fact**, and only then delivers a clean answer. It reasons
> **top-down from the bigger picture**, never bottom-up from the routine surface.
>
> **Law of the engine:** *more parameters of comparison → more outcome.*

It is **not** a new LLM. It is a **control layer around a base model** — archetypal
grounding + multi-loop verification + the user's own fed brain. A new *way of
thinking*, not a bigger model.

---

## 1. THE THREE MEMORIES (the brain's substrate)

| Memory | What it is | In this repo |
|--------|------------|--------------|
| **Reflex** — muscle memory | the user's fed corpus + example bank ("clone me") | `persona.py` + `memory.py` |
| **Instinct** — wisdom bank | holy books, proverbs, archetypes (eternal examples) | `wisdom.py` |
| **Eyes** — live fact | web/current data (Tavily/search), keeps the example honest | `engine.grounding` hook |

**Brain = reflex + instinct + eyes + the loop that binds them.**

### The grounding pyramid (nothing at the top is allowed to float)
```
        DELIVERED ANSWER          ← what the user sees (clean, public-safe)
            ▲ backed by
        LIVE FACT (web/today)
            ▲ backed by
   WISDOM / ARCHETYPE / EXAMPLE   ← eternal pattern (holy books, proverbs)
            ▲ backed by
   YOUR CORES / ENGINES / CASES   ← muscle memory (your fed files)
            ▲ backed by
        RAW SOURCE (foundation)   ← unrefined origin (1→5→20 pyramid)
```

---

## 2. ARCHITECTURE — SB + URR, the pyramid of brains

Two tightly-coupled layers (ownership is hard):

- **SB (Sourceborn)** — the working engine. Owns Point Zero, all stages/nodes,
  loops, Halt creation, GapTable, ProofLedger, Wild Path, Master Log, final
  delivery, public-safe output.
- **URR (Unreal→Real)** — the integrity layer. A **micro-pass verification gate**
  called through the run: classify, force-fit score, evidence check, reality
  anchor, dual-path halt, synthetic tagging, human gate. **URR never delivers;
  SB never skips URR.**

### Node map (the "7025 / Omni" core)
- **70 SB points** across **8 stages** (scalable to 100).
- **25 URR points** in 5 blocks of 5 (scalable to 40).
- **Every node is a local brain** with **pyramid filtering**:
  `1 (Node) → 5-10 (Main) → 10-20 (Sub) → 20-30 (Micro)` for SB;
  `5 → 10-15` for URR.
- **One Master Log** records everything (Principle 13).
- **Weekly brain update** (every Monday) for every local brain.
- **Full interconnection** — any point can loop back to any earlier point.

#### The 8 SB stages
| Stage | SB range | Focus |
|------|----------|-------|
| 1 | SB-01…08 | Foundation & Intake (Point Zero lock, noise strip, classify, first memory write) |
| 2 | SB-09…18 | Human Core & Psychology (Affect, Core Gate 6 lenses, Shadow, identity, power, wounds) |
| 3 | SB-19…28 | Truth, Doubt & Pressure (Truth Pressure Test, Doubt Engine, Falsifier, Witness) |
| 4 | SB-29…36 | Evidence & Validation (Evidence Ledger, source tags, domain audit, live grounding) |
| 5 | SB-37…44 | Connection, Dot & Memory (Dot Connection, Cross-Domain Fusion, merges, new params) |
| 6 | SB-45…52 | Synthetic, Invention & New Parameters (5 fuels, invention seeds, parameter generation) |
| 7 | SB-53…60 | Risk, Ethics & Human Control (Risk gate, logic walls, override ledger, reality re-anchor) |
| 8 | SB-61…70 | Output, Memory Update & Brain Maintenance (Master Log, weekly update, final output, human halt) |

> The full per-node list lives in `src/sourceborn/nodes.py` (machine-readable).

#### The 25 URR blocks
URR-01…05 Early Verification · URR-06…10 Evidence & Synthetic Audit ·
URR-11…15 Risk & Human Gate · URR-16…20 Memory & Parameter Integrity ·
URR-21…25 Final Integrity & Closure.

---

## 3. THE 25 PRINCIPLE BACKBONE (non-negotiable)

1. **Human Final Authority** — human can halt, reverse, inject, reject anything.
2. **Non-Resolution is Valid** — not solving can be the correct state.
3. **Synthetic Must Be Tagged** — every synthetic output carries proof-debt + expiry.
4. **Memory is High-Parameter** — store rich parameters, not just summaries.
5. **Merge Only on Real Value** — merge only when it creates stronger understanding.
6. **Local Brain Per Node** — every SB and URR node has its own updating brain.
7. **Pyramid Filtering at Every Node** — data organised Node → Main → Sub → Micro.
8. **Full Interconnection** — any point can connect to any other point.
9. **URR as Integrity Layer** — deep verification + human gate.
10. **Automatic Memory Write** — writing follows rules, not manual effort.
11. **New Parameter Generation** — create new parameters when data doesn't fit.
12. **Weekly Brain Update** — local brains update every Monday.
13. **Master Log is Sacred** — all parameters, mergers, sources recorded.
14. **Raw Source Never Changes** — original input stays untouched.
15. **Affect is First-Class Data** — feeling/emotion are usable data.
16. **Doubt Engine is Mandatory** — the strongest conclusion must be attacked.
17. **Witness Node is Active** — the engine surfaces its own blind spots.
18. **Cross-Domain Connection** — actively find patterns across domains.
19. **Risk Gate is Non-Bypassable** — high-risk moves require human approval.
20. **Reality Re-Anchor** — major conclusions checked against Point Zero.
21. **Embodied Check** — body/intuition resistance is valid data.
22. **Proof Debt Tracking** — all assumptions carry visible debt.
23. **Human Override Ledger** — every human decision recorded with reason.
24. **Scalable to 100+ Nodes** — can grow beyond 70 SB + 25 URR.
25. **Sequence + Tree Hybrid** — works as both a sequence and an interconnected tree.

---

## 4. KEY MECHANISMS

### Point Zero
Unlimited starting position **before** forced selection. **Not** current real-world
status (that lives in Reality Check / Evidence). `Point Zero with Product` =
verification only (result returns to original Point Zero). `Point Zero + Product` =
accepted result, only after verification/acceptance.

### Halt → New Loop (hard rule)
Failure is never failure — it becomes a **Halt Point**, and every Halt must open at
least one loop before the stage can close. Mapping (`src/sourceborn/halt_map.py`):

| Halt | Loop |
|------|------|
| Evidence | Evidence Loop |
| Language | Pattern / Intent-Condition-Power Loop |
| Logic | Contradiction / Falsifier Loop |
| Product | Product Route / Review Loop |
| Mystery | Mystery Loop |
| Status / Safety | Admin Review Loop (+ Hold) |
| Public Claim | Public Extraction Loop |
| Reality | Reality Check Loop |
| Contradiction | Contradiction Loop |

### The RGL — Recursive Genesis Loop
The invariant container; structure stays constant while content compounds. Six
sub-loops: **Origin** (Point Zero→Source), **Recognition** (Pattern→Intent),
**Validation** (Evidence→Halt), **Generation** (Stage Addition→Mystery/Invention),
**Resolution** (Outcome→Review), **Return** (Point Zero with Product → Next Loop →
Point Zero + Product; re-opens up to 100×). PZ in loop *n* carries the product of
loop *n-1*. Runs on a poem, a contract, a scripture, or one sentence.

### Synthetic Fuel Injector (caged)
Five reality-warpers, **all tagged `[SYNTHETIC]` until promoted by evidence**:
Hypothetical Simulation · Counterfactual Friction · Heuristic Fiction · Working
Fiction · Apostatic Inversion.

### Core Gate — six lenses
Mask & Payoff · Wound & Threat · Loyalty & Drive · Desire & Fear · Pain & Payoff ·
Meaning & Identity. (Affect is first-class data.)

### Evidence tags (exactly one per claim)
`FACT` (visible, supported) · `REVIEW` (plausible, unproven) · `SYNTHETIC` (useful
fiction until promoted) · `RUMOR` (pressure-test only) · `OPEN` (deliberately
unresolved).

### Authority hierarchy
Human (absolute) → Witness Node → Doubt Engine → Truth Pressure Test → Reality
Anchor (dual) → Engine (analysis layer).

---

## 5. PARAMETERS — "more parameters, more outcome"

- **64-parameter bank (P001–P064)** — what the engine *stores* about anything
  (`src/sourceborn/parameters.py`). Master formula:
  `Raw Symbol → Role → Pressure → Emotion → Action → Transformation → Cost → Loop → Evidence Status`.
- **Comparison axes (extensible forever)** — how the engine *compares* a question
  to its deepest example: Intent · Pattern · Motive/Shadow · Precedent/Archetype ·
  Moral/Sacred line · Consequence · Time · Scale · Opposite/Inversion · Falsifier ·
  Simplicity/Key-in-hand · Emotion · Power/Condition. Add axes → multiply outcome.

---

## 6. OPERATING FLOW (what one run does)

```
USER ASKS
 1. READ & PROTECT     → lock raw source (Point Zero, Noise Stripper)
 2. ANALYSE TRUE ASK   → what is really being asked under the words?
 3. DECOMPOSE          → split into micro-questions / claims / gaps
 4. BIGGER-PICTURE TRIAGE → routine (key-in-hand) vs deep (full loop)
 5. EXAMPLE & WISDOM MATCH → deepest matching example (wisdom + your corpus),
                              compared across many axes
 6. LIVE GROUNDING     → bind eternal example to present fact (web)
 7. VERIFY (URR)       → truth-chain, contradictions, force-fit, penetration,
                          confidence; if weak → discard + fuel, loop again
 8. PLACE WELL         → arrange verified pieces in clean order (the lanes)
 9. DELIVER            → public-safe only if asked; honest about the unknown;
                          offer the next step; LEARN the example (clone compounds)
```

### Output lanes (URR-07)
Reality Path · Wild Path / Personal Theory · Classification · Sourceborn Sequence ·
Proof Loop · Contradiction Loop · Mystery Loop · Invention Loop · Data Bank ·
Public Extraction (only when asked) · Carry-Forward (when chat gets long).

Every output carries: classification, evidence tag, **confidence**, **reversibility**,
**falsifier**, penetration score, open question.

---

## 7. SAFETY BOUNDARY (private + unrestricted, honestly)

"Unrestricted" means (per URR-07 / Secureborn): **no forced rejection at intake, no
forced public-safe framing for private exploration, no killing of the Wild Path, no
forced conclusion.** It does **not** mean removing the hard line the cores
themselves keep:

- **Hard blocks (refused — still mapped safely, never executed):** harmful/illegal
  execution, weapons, fraud, medical misuse, guaranteed financial predictions,
  explicit sexual/nude generation.
- **Soft blocks (allowed as theory/history/fiction with a confirmation gate):**
  high-risk topics, sensitive claims without strong evidence.

When blocked, the engine still maps: *what the claim is · why execution is blocked ·
what can be discussed safely · what theory path exists · what evidence would be
needed · what public claim is not allowed.*

---

## 8. LINEAGE (all names are one engine)

Raw Definition Engine / RD World → ARD (Autonomous Reasoning, 3.0 → 3.1 LEAN+
"Penetration Engine") + RGL (Recursive Genesis Loop) → URR-07 (private engine) →
Secureborn → **Sourceborn / SBUR** → the **70 SB + 25 URR "Omni / 7025" core**.
The Riemann "Mirror" work is the engine *run on a hard problem* (a proof-of-engine),
not the engine itself.

---

## 9. IMPLEMENTATION STATUS (spec ↔ code)

The engine is built and live (Render web app). Each stage maps to real code:

| Stage / feature | Module |
|---|---|
| 1 Intake · Point Zero · noise strip | `engine.py` |
| 2 Core Gate — six lenses | `core_gate.py` |
| 3 Doubt Engine · Falsifier · Witness | `doubt.py` |
| 4 Evidence ladder · source tags | `evidence.py` |
| 5 Dot-Connection · human-gated Merge | `dots.py` |
| 6 Synthetic Fuel Injector (5 caged fuels) | `fuel.py` |
| 7 Risk gate / Reality Re-Anchor / Drift / Embodied / Non-Resolution | `safety.py`, `drift_guard.py`, `engine.py` |
| 8 Master Log · final output · weekly brain update | `memory.py`, `scheduler.py` |
| RGL recursive loop | `engine.run_recursive` |
| 95 local brains + settings | `brains.py` |
| 3 memories (corpus / wisdom / live) | `persona.py`, `wisdom.py`, `grounding.py` |
| Base models (Claude / Grok / OpenAI) | `llm.py` |
| Web app + API + deploy | `server.py`, `app.py`, `render.yaml` |

Open for future depth: real scripture/proverb Wisdom Bank corpus, model-backed URR
micro-pass, richer interconnection-graph UI.

---

*End of canonical core. The machine-readable version of the node map, parameters,
halts and loops lives in `src/sourceborn/`. This document and the code are meant to
stay in sync.*
