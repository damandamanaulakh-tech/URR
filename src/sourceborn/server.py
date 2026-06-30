"""Sourceborn web service — a zero-dependency HTTP server (stdlib only).

Runs the engine behind a dark dashboard and a JSON API, so it can be deployed
to Render (or any host) with nothing to install but Python.

    python -m sourceborn.server          # local: http://localhost:8000
    PORT=10000 python -m sourceborn.server

Endpoints:
    GET  /            -> the dashboard UI
    GET  /health      -> model + brain status
    GET  /brains /brain /graph
    GET  /memory/report          -> what is stored in each memory node (live)
    GET  /snapshots /snapshot    -> saved memory snapshots (current vs older)
    POST /ask         -> per-node SB<->URR walk + human review queue
    POST /review      -> approve / add-data / re-loop a held node
    POST /ingest      -> feed text into the brain
    POST /upload      -> review an uploaded file (txt/md/csv/docx/xlsx/pdf)
    POST /snapshot    -> save a memory snapshot
    POST /brains/update /brain/settings

Set ANTHROPIC_API_KEY / XAI_API_KEY / OPENAI_API_KEY (env vars on Render) to turn
on real reasoning. Render's disk is ephemeral; for persistent memory mount a
Render Disk at ``.sourceborn`` or use a DB (docs/RECOMMENDATION.md, Phase 3).
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import scheduler
from .engine import SourcebornEngine, NO_LIVE
from .extract import extract_text
from .llm import (get_model, model_status, generate_image,
                  CaptureModel, LocalBridgeModel, LocalCaptured)
from .models import _now

SB_ROOT = os.environ.get("SB_ROOT", ".sourceborn")
ENGINE = SourcebornEngine(root=SB_ROOT)
SNAP_DIR = os.path.join(SB_ROOT, "_snapshots")


def _ingest_text(name: str, text: str) -> dict:
    """Feed one note/file into the brain (memory + clone), and persist it to the
    corpus folder on disk if SB_INGEST_CORPUS is set (e.g. a Render disk)."""
    from .enums import Classification, EvidenceTag
    from .models import MemoryEntry, RawSource
    raw = RawSource(text=text, origin=f"upload:{name}").lock()
    ENGINE.memory.write("SB-07", MemoryEntry(
        node_id="SB-07", raw_source_id=raw.raw_source_id, content=text[:4000],
        classification=Classification.REVIEW_ONLY.value,
        evidence_tag=EvidenceTag.REVIEW.value, tags=["corpus", name],
        parameters={"chars": len(text)}), name="First Memory Write")
    ENGINE.persona.learn(question=name, answer=text[:1200], note="fed via app")
    folder = os.environ.get("SB_INGEST_CORPUS")
    if folder:
        os.makedirs(folder, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "note"
        with open(os.path.join(folder, safe + ".txt"), "w", encoding="utf-8") as f:
            f.write(text)
    return {"memory": ENGINE.memory.stats(), "examples": len(ENGINE.persona.examples)}


def _library(preview: int = 160) -> dict:
    """List the files/notes fed into the brain — the user's 'library'."""
    items = []
    folder = os.environ.get("SB_INGEST_CORPUS")
    if folder and os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            p = os.path.join(folder, fn)
            if os.path.isfile(p):
                try:
                    t = open(p, encoding="utf-8", errors="ignore").read()
                except Exception:
                    t = ""
                items.append({"name": fn, "chars": len(t), "preview": t[:preview]})
    if not items:                       # fallback: the clone's learned examples
        for ex in list(getattr(ENGINE.persona, "examples", []))[-50:]:
            items.append({"name": getattr(ex, "question", "note"),
                          "chars": len(getattr(ex, "answer", "") or ""),
                          "preview": (getattr(ex, "answer", "") or "")[:preview]})
    return {"files": items, "count": len(items),
            "folder": folder or "(in-memory — set SB_INGEST_CORPUS to persist files)"}


def _memory_report(limit: int = 3) -> dict:
    """A snapshot of what each memory node holds — counts, last update, and the
    most recent entries (so the user can see exactly what was added, and compare
    to older snapshots)."""
    mem = ENGINE.memory
    bdir = os.path.join(mem.root, "brains")
    nodes = []
    if os.path.isdir(bdir):
        for nid in sorted(os.listdir(bdir)):
            b = mem.brain(nid)
            if b.meta.get("entry_count", 0) == 0:
                continue
            cfg = ENGINE.brains.get(nid)
            entries = b.read_all()
            recent = [{"content": (e.content or "")[:180], "tags": e.tags,
                       "evidence_tag": e.evidence_tag, "classification": e.classification}
                      for e in entries[-limit:]]
            nodes.append({"id": nid, "name": (cfg.name if cfg else b.meta.get("name", "")),
                          "entry_count": b.meta.get("entry_count", len(entries)),
                          "last_update": b.meta.get("last_update", ""),
                          "recent": recent})
    return {"at": _now(), "totals": mem.stats(), "nodes": nodes}


def _save_snapshot(name: str = "") -> dict:
    os.makedirs(SNAP_DIR, exist_ok=True)
    rep = _memory_report()
    sid = re.sub(r"[^0-9A-Za-z]", "", rep["at"])[:14] or str(len(os.listdir(SNAP_DIR)))
    rep["name"] = name.strip() or f"snapshot {sid}"
    rep["id"] = sid
    with open(os.path.join(SNAP_DIR, sid + ".json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False)
    return {"ok": True, "id": sid, "name": rep["name"], "total": rep["totals"]}


def _list_snapshots() -> list[dict]:
    if not os.path.isdir(SNAP_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(SNAP_DIR), reverse=True):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(SNAP_DIR, fn), encoding="utf-8") as f:
                    d = json.load(f)
                out.append({"id": d.get("id", fn[:-5]), "name": d.get("name", fn),
                            "at": d.get("at", ""), "total": d.get("totals", {})})
            except Exception:
                continue
    return out


PAGE = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Sourceborn</title><style>
:root{
 --bg:#070809;--panel:#0f1219;--panel2:#0b0e14;--elev:#141826;
 --line:#1c2230;--line2:#262d3d;--ink:#eef2f8;--mut:#7d8699;--mut2:#5b6477;
 --acc:#7c8bff;--ok:#34d399;--warn:#fbbf24;--bad:#f87171;--hl:#ffb454;--gd:#7ee787;
 --grad:linear-gradient(135deg,#7c8bff,#a78bfa 60%,#f0abfc);
 --shadow:0 14px 36px -16px rgba(0,0,0,.75);--ring:0 0 0 3px rgba(124,139,255,.25)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;color:var(--ink);font:15px/1.55 'Inter',-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;
 -webkit-font-smoothing:antialiased;
 background:radial-gradient(900px 520px at 85% -8%,rgba(124,139,255,.14),transparent 60%),
 radial-gradient(720px 520px at 0 0,rgba(167,139,250,.10),transparent 55%),var(--bg)}
::selection{background:rgba(124,139,255,.3)}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:10px;border:2px solid transparent;background-clip:padding-box}
.app{max-width:1240px;margin:0 auto;padding:0 18px 60px}
.topbar{position:sticky;top:0;z-index:20;display:flex;justify-content:space-between;align-items:center;gap:12px;
 padding:14px 4px;margin-bottom:8px;flex-wrap:wrap;
 backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
 background:linear-gradient(180deg,rgba(7,8,9,.86),rgba(7,8,9,.35));border-bottom:1px solid var(--line)}
.brand{display:flex;gap:12px;align-items:center}
.logo{width:38px;height:38px;border-radius:11px;background:var(--grad);display:grid;place-items:center;overflow:hidden;
 box-shadow:0 6px 18px -6px rgba(124,139,255,.6)}
.logo img{width:38px;height:38px;object-fit:cover;display:block}
.brand .name{font-size:18px;font-weight:700;letter-spacing:-.01em}
.brand .tag{font-size:12px;color:var(--mut)}
.stats{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{display:inline-flex;gap:7px;align-items:center;background:var(--panel);border:1px solid var(--line);
 border-radius:999px;padding:6px 12px;font-size:12.5px;color:var(--mut)}
.pill b{color:var(--ink);font-weight:600}
.pdot{width:8px;height:8px;border-radius:50%;background:var(--mut2)}
.pdot.live{background:var(--ok);box-shadow:0 0 0 3px rgba(52,211,153,.18)}
.grid{display:grid;grid-template-columns:300px 1fr;gap:18px;align-items:start}
@media(max-width:880px){.grid{grid-template-columns:1fr}}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
 border-radius:16px;padding:18px;margin:0 0 16px;box-shadow:var(--shadow);transition:border-color .15s}
.card:hover{border-color:var(--line2)}.side .card{padding:14px}
.k{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);
 margin:0 0 11px;display:flex;align-items:center;gap:8px}.k .num{margin-left:auto;color:var(--mut2)}
.side .acc{margin:0 0 10px}
.side .acc>summary{font-size:11px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--ink);
 padding:9px 0;border-bottom:1px solid var(--line)}
.side .sec{padding:11px 2px 4px}
.hero{padding:6px;background:linear-gradient(180deg,var(--elev),var(--panel2));border-color:var(--line2)}
.hero .inner{background:var(--panel2);border:1px solid var(--line);border-radius:13px;padding:14px}
textarea,input,select{font:inherit;color:var(--ink)}
#q{width:100%;background:transparent;border:0;color:var(--ink);min-height:84px;resize:vertical;outline:none;font-size:16px;line-height:1.5}
#q::placeholder{color:var(--mut2)}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px;padding-top:12px;border-top:1px solid var(--line)}
.field{display:inline-flex;gap:7px;align-items:center;background:var(--panel);border:1px solid var(--line);
 border-radius:10px;padding:0 10px;height:38px;color:var(--mut);font-size:13px}
.field select,.field input{background:transparent;border:0;outline:none;color:var(--ink);font-size:13px}
.field:focus-within{border-color:var(--acc);box-shadow:var(--ring)}
button.primary{height:38px;padding:0 18px;border:0;border-radius:10px;background:var(--grad);color:#0a0f1f;
 font-weight:700;font-size:14px;cursor:pointer;display:inline-flex;gap:8px;align-items:center;
 box-shadow:0 8px 20px -8px rgba(124,139,255,.7);transition:.15s}
button.primary:hover{filter:brightness(1.08);transform:translateY(-1px)}
button.primary:disabled{opacity:.6;cursor:default;transform:none}
.btn{height:34px;padding:0 13px;border:1px solid var(--line2);border-radius:9px;background:var(--panel);
 color:var(--ink);font-weight:600;font-size:13px;cursor:pointer;transition:.15s}
.btn:hover{border-color:var(--acc);color:#fff}.btn.sm{height:30px;padding:0 10px;font-size:12px}
.iconbtn{width:38px;height:38px;border:1px solid var(--line);border-radius:10px;background:var(--panel);
 color:var(--ink);cursor:pointer;font-size:15px}.iconbtn:hover{border-color:var(--acc)}.iconbtn.on{color:var(--bad);border-color:var(--bad)}
.switch{display:inline-flex;gap:9px;align-items:center;cursor:pointer;color:var(--mut);font-size:13px;user-select:none}
.switch input{display:none}
.switch .track{width:38px;height:22px;border-radius:999px;background:var(--line2);position:relative;transition:.18s;flex:none}
.switch .track:after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#cfd6e6;transition:.18s}
.switch input:checked+.track{background:var(--acc)}
.switch input:checked+.track:after{transform:translateX(16px);background:#fff}
.spin{display:inline-block;width:15px;height:15px;border:2px solid rgba(10,15,31,.35);
 border-top-color:#0a0f1f;border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.status{color:var(--mut);font-size:13px}
.chips{display:flex;gap:8px;flex-wrap:wrap;padding:12px 8px 6px}
.chip{font-size:12.5px;color:var(--mut);background:var(--panel);border:1px solid var(--line);
 border-radius:999px;padding:6px 12px;cursor:pointer;transition:.15s}
.chip:hover{border-color:var(--acc);color:var(--ink)}
.ans{white-space:pre-wrap;font-size:15.5px;line-height:1.65}
.badges{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}
.badge{display:inline-flex;gap:6px;align-items:center;font-size:12px;border-radius:999px;padding:4px 11px;
 background:var(--panel);border:1px solid var(--line);color:var(--mut)}
.badge b{color:var(--ink);font-weight:600}
.badge.ok{border-color:rgba(52,211,153,.4);color:#9ff0d0}
.badge.warn{border-color:rgba(251,191,36,.4);color:#ffe2a3}
.badge.bad{border-color:rgba(248,113,113,.4);color:#ffc4c4}
.meter{height:6px;border-radius:999px;background:var(--line);overflow:hidden;margin:12px 0 4px}
.meter>i{display:block;height:100%;border-radius:999px;background:var(--grad);transition:width .4s}
.lane{border-left:2px solid var(--line2);padding:4px 0 4px 13px;margin:8px 0;color:var(--ink)}
.lane b{color:#cdd5e6}
.fals{margin-top:10px;color:var(--mut);font-size:13.5px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:9px 12px}
.why{margin-top:11px;font-size:13.5px;color:#ffe2a3;background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.32);border-radius:10px;padding:9px 12px}
.vd{font-size:11px}.vd.pass{color:var(--ok)}.vd.hold{color:var(--warn)}
.memok{font-size:11px;color:var(--gd);margin-left:6px}
.hold{border:1px solid var(--line);background:var(--panel);border-radius:11px;padding:12px;margin:9px 0}
.fivew{display:grid;grid-template-columns:1fr 1fr;gap:6px 14px;margin:8px 0;font-size:12.5px;color:var(--mut)}
.fivew b{color:var(--acc);font-weight:600;margin-right:5px}
.hactions{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.tag{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:3px 4px 0 0;font-size:12px;color:var(--mut)}
.hl{color:var(--hl)}.gd{color:var(--gd)}.muted{color:var(--mut)}
.pyr{display:flex;flex-direction:column;gap:5px;align-items:center}
.plvl{border:1px solid var(--line);background:var(--panel);border-radius:9px;padding:6px 8px;text-align:center;
 font-size:11px;color:var(--mut);transition:.25s;width:100%}
.plvl.on{border-color:var(--acc);background:linear-gradient(180deg,rgba(124,139,255,.18),rgba(124,139,255,.06));
 color:var(--ink);box-shadow:0 0 18px -6px rgba(124,139,255,.5)}
.mem{display:flex;flex-direction:column;gap:9px}
.memrow{display:flex;gap:10px;align-items:center;font-size:13px;color:var(--mut)}
.memrow b{color:var(--ink);font-weight:600}
.md{width:9px;height:9px;border-radius:50%;flex:none}
.md.r{background:#7c8bff}.md.i{background:#34d399}.md.e{background:#ffb454}
.hist a{display:block;color:var(--mut);font-size:13px;padding:8px 0;border-bottom:1px solid var(--line);
 cursor:pointer;text-decoration:none;transition:.12s}.hist a:last-child{border-bottom:0}
.hist a:hover{color:var(--ink);padding-left:4px}
.in{width:100%;background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:9px 11px;outline:none;font:inherit;color:var(--ink)}
.in:focus{border-color:var(--acc);box-shadow:var(--ring)}.in::placeholder{color:var(--mut2)}
.rep{font-size:12.5px}.repn{border:1px solid var(--line);border-radius:10px;padding:9px 11px;margin:7px 0;background:var(--panel)}
.repn .h{display:flex;justify-content:space-between;color:var(--ink);font-weight:600}
.repn .e{color:var(--mut);margin-top:4px;border-top:1px dashed var(--line);padding-top:4px}
details summary{cursor:pointer;color:var(--mut);font-size:13px;padding:4px 0;list-style:none}
details summary::-webkit-details-marker{display:none}
details summary:before{content:"\25b8  ";color:var(--mut2)}
details[open]>summary:before{content:"\25be  "}
.bset{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0}
.bset select{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 8px;color:var(--ink)}
.trace{font:12px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut);white-space:pre-wrap;word-break:break-word}
.fade{animation:fade .35s ease}@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style></head><body><div class=app>

<header class=topbar>
  <div class=brand>
    <div class=logo><img src="https://avatars.githubusercontent.com/u/284725680?v=4" alt="" onerror="this.remove()"></div>
    <div><div class=name>Sourceborn</div><div class=tag>eternal example &middot; present fact &middot; more parameters, more outcome</div></div>
  </div>
  <div class=stats>
    <span class=pill id=mpill><span class=pdot id=pdot></span> <b id=mname>offline</b></span>
    <span class=pill>brains <b id=bpill>95</b></span>
    <span class=pill id=wpill>weekly <b>&mdash;</b></span>
  </div>
</header>

<div class=grid>
<!-- LEFT: read-only — history + library (memories, pyramid, reports, node brains) -->
<nav class=side>
  <div class=card><div class=k>History</div><div class=hist id=hist><span class=muted>empty</span></div></div>
  <div class=card>
    <details class=acc open><summary>Library</summary>
      <div class=sec>
        <div class=k>Three memories</div>
        <div class=mem>
          <div class=memrow><span class="md r"></span><div><b>Reflex</b> &middot; your corpus &amp; clone</div></div>
          <div class=memrow><span class="md i"></span><div><b>Instinct</b> &middot; wisdom bank</div></div>
          <div class=memrow><span class="md e"></span><div><b>Eyes</b> &middot; live fact</div></div>
        </div>
      </div>
      <details class=acc><summary>Engine pyramid</summary><div class=sec><div class=pyr id=pyr></div></div></details>
      <details class=acc><summary>Reports &amp; snapshots</summary><div class=sec>
        <div class=hactions><button class="btn sm" onclick=loadReport()>Memory report</button>
          <button class="btn sm" onclick=saveSnapshot()>Save snapshot</button></div>
        <div class=status id=repstat style="margin-top:6px"></div>
        <div id=snaps style="margin-top:6px"></div>
      </div></details>
      <details class=acc><summary>Node brains (<span id=bcount>0</span>)</summary><div class=sec>
        <div class=hactions><button class="btn sm" onclick=weeklyUpdate()>Weekly update</button><span class=status id=bstat></span></div>
        <div id=brains style="margin-top:6px"></div>
      </div></details>
      <details class=acc><summary>Files (<span id=lcount>0</span>)</summary><div class=sec>
        <div class=hactions><button class="btn sm" onclick=loadLibrary()>Refresh</button><span class=status id=lstat></span></div>
        <div id=libfiles style="margin-top:6px"></div>
      </div></details>
    </details>
  </div>
</nav>

<!-- RIGHT: editable — ask, answer, review queue, feed the brain -->
<main>
  <section class="card hero">
    <div class=inner>
      <textarea id=q placeholder="Ask anything — a question, a mess, a half-thought…   ⌘/Ctrl + Enter to run"></textarea>
      <div class=toolbar>
        <button id=go class=primary onclick=ask()><span id=goico>&#9654;</span><span id=golbl>Run engine</span></button>
        <button class=iconbtn id=mic title="voice to text" onclick=dictate()>&#127908;</button>
        <span class=field><select id=model title="base model"></select></span>
        <span class=field id=localwrap style="display:none"><select id=localmodel title="on-device model — runs on your GPU, nothing leaves your machine"></select></span>
        <label class=switch title="keep the thread — fold the last answer into the next ask"><input type=checkbox id=cont checked><span class=track></span> continue thread</label>
        <span class=status id=status></span>
      </div>
      <div class=toolbar style="border:0;padding-top:8px">
        <span class=field><input type=file id=file multiple></span>
        <button class=btn onclick=doUpload()>Review file</button>
        <button class=btn onclick=genImage()>Generate image</button>
        <span class=status id=ustat></span>
      </div>
    </div>
    <div class=chips id=examples></div>
  </section>
  <div id=out></div>
  <div class=card><div class=k>Feed the brain</div>
    <input id=fname class=in placeholder="name (optional)" style="margin-bottom:7px">
    <textarea id=ftext class=in placeholder="paste a note, thought, or core…" style="min-height:60px;resize:vertical"></textarea>
    <div class=toolbar style="border:0;padding:0;margin-top:9px"><button class=btn onclick=feed()>Add to memory</button><span class=status id=fstat></span></div>
  </div>
</main>
</div>

<style>#model option,select option{color:#0b1020;background:#fff}#model option:disabled,select option:disabled{color:#9aa3b2}</style>
<script>
const STAGES=[["1","Foundation & Intake"],["2","Human Core"],["3","Truth & Doubt"],["4","Evidence"],
["5","Connection & Memory"],["6","Synthetic & Invention"],["7","Risk & Control"],["8","Output & Update"]];
const EXAMPLES=[];
// On-device models (run in the browser on the user's own GPU via WebLLM). IDs
// come from WebLLM's prebuilt list; the engine still wraps every answer.
const LOCAL_MODELS=[
  ['Llama-3.2-1B-Instruct-q4f16_1-MLC','Llama 3.2 1B · fast (~0.9 GB)'],
  ['Qwen2-0.5B-Instruct-q4f32_1-MLC','Qwen2 0.5B · fastest (~0.6 GB)'],
  ['Phi-3-mini-4k-instruct-q4f16_1-MLC','Phi-3 mini · stronger (~2.2 GB)'],
  ['Gemma-2B-it-q4f32_1-MLC','Gemma 2B · alt (~1.4 GB)'],
];
function stageOf(id){let n=parseInt((id||'').replace('SB-',''));if(!n)return 0;
  return n<=8?1:n<=18?2:n<=28?3:n<=36?4:n<=44?5:n<=52?6:n<=60?7:8}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function confClass(c){c=(''+c).toLowerCase();return c=='high'?'ok':c=='medium'?'warn':c=='low'?'bad':''}
function confPct(c){c=(''+c).toLowerCase();return c=='high'?92:c=='medium'?62:c=='low'?32:50}
let HIST=JSON.parse(localStorage.getItem('sb_hist')||'[]');
let LASTQ='',LASTD=null,LASTANS='',THREAD=[];

const HASGPU=!!(navigator.gpu);
fetch('/health').then(r=>r.json()).then(d=>{
  const sel=document.getElementById('model');
  const labels={offline:'Offline (no key)',claude:'Claude (deep)',grok:'Grok (raw)',openai:'OpenAI',openrouter:'OpenRouter',local:'Local — private (your GPU)'};
  for(const [k,ok] of Object.entries(d.models)){
    const o=document.createElement('option');o.value=k;
    let lab=labels[k]||k;
    if(k==='local'){ lab+=HASGPU?'':' — needs WebGPU'; if(!HASGPU)o.disabled=true; }
    else { lab+=(ok?'':' — add key'); if(!ok&&k!=='offline')o.disabled=true; }
    o.textContent=lab;
    if(k===d.model)o.selected=true;sel.appendChild(o);
  }
  sel.addEventListener('change',syncLocalUI); syncLocalUI();
  document.getElementById('mname').textContent=(labels[d.model]||d.model).split(' ')[0];
  if(d.model!=='offline')document.getElementById('pdot').classList.add('live');
  document.getElementById('bpill').textContent=d.brains||95;
  const set=d.weekly&&d.weekly.last_weekly_update;
  document.getElementById('wpill').innerHTML='weekly <b>'+(set?'active':'due')+'</b>';
}); drawPyr(new Set(),{}); drawHist(); loadLibrary(); initLocalPicker();
document.getElementById('examples').innerHTML=EXAMPLES.map(e=>'<span class=chip>'+esc(e)+'</span>').join('');
document.querySelectorAll('#examples .chip').forEach((c,i)=>c.onclick=()=>{
  const q=document.getElementById('q');q.value=EXAMPLES[i];q.focus()});

function drawPyr(firedStages,counts){
  firedStages=firedStages||new Set(); counts=counts||{};
  let html='';
  for(let i=STAGES.length-1;i>=0;i--){
    const s=STAGES[i], n=+s[0], on=firedStages.has(n), w=44+(8-n)*7;
    const c=counts[n]?(' · '+counts[n]+' fired'):'';
    html+='<div class="plvl'+(on?' on':'')+'" style="width:'+w+'%">SB'+n+' '+esc(s[1])+c+'</div>';
  }
  html+='<div class=plvl style="width:100%;opacity:.65">URR · 25 verification gates</div>';
  document.getElementById('pyr').innerHTML=html;
}
function drawHist(){
  const h=document.getElementById('hist');
  h.innerHTML=HIST.length?HIST.slice(0,12).map((q,i)=>`<a onclick="document.getElementById('q').value=${JSON.stringify(q).replace(/"/g,'&quot;')}">${esc(q.slice(0,60))}</a>`).join(''):'<span class=muted>empty</span>';
}
function busy(on){
  const go=document.getElementById('go'),ic=document.getElementById('goico'),lb=document.getElementById('golbl');
  go.disabled=on; lb.textContent=on?'Running…':'Run engine';
  ic.className=on?'spin':''; ic.innerHTML=on?'':'&#9654;';
  document.getElementById('status').textContent=on?'running SB + URR…':'';
}
function ctx(){ if(!document.getElementById('cont').checked) return '';
  return THREAD.slice(-3).map(t=>'You asked: '+t.q+'\nReply was: '+t.a).join('\n\n'); }
function initLocalPicker(){
  const lm=document.getElementById('localmodel'); if(!lm)return;
  const saved=localStorage.getItem('sb_local_model')||LOCAL_MODELS[0][0];
  lm.innerHTML=LOCAL_MODELS.map(([v,t])=>'<option value="'+v+'">'+esc(t)+'</option>').join('');
  lm.value=saved; if(lm.value!==saved)lm.value=LOCAL_MODELS[0][0];
  lm.addEventListener('change',()=>localStorage.setItem('sb_local_model',lm.value));
}
function syncLocalUI(){
  const isLocal=document.getElementById('model').value==='local';
  const w=document.getElementById('localwrap'); if(w)w.style.display=isLocal?'':'none';
}
function waitForLocal(ms){            // the WebLLM module loads async — give it a moment
  return new Promise((res,rej)=>{
    if(window.__localLLM)return res();
    let t=0; const iv=setInterval(()=>{
      if(window.__localLLM){clearInterval(iv);res();}
      else if((t+=100)>=ms){clearInterval(iv);rej(new Error('on-device engine library still loading — try again in a moment'));}
    },100);
  });
}
async function ensureLocalModel(){
  if(!navigator.gpu)throw new Error('this browser has no WebGPU — use Chrome/Edge 121+ or Safari 18+');
  await waitForLocal(8000);
  const st=document.getElementById('status');
  await window.__localLLM.load(p=>{
    const pct=Math.round(((p&&p.progress)||0)*100);
    st.textContent=(p&&p.text)?('on-device model · '+p.text):('loading on-device model… '+pct+'%');
  });
}
async function askLocal(q){
  const st=document.getElementById('status');
  st.textContent='engine preparing prompt…';
  const r1=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({question:q,model:'local',context:ctx()})});
  const d1=await r1.json();
  if(!d1||d1.stage!=='need_local')return d1;      // server already answered (fallback)
  await ensureLocalModel();
  st.textContent='thinking on your GPU…';
  const answer=await window.__localLLM.generate(d1.system,d1.prompt);
  st.textContent='running SB + URR…';
  const r2=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({question:q,model:'local',context:ctx(),local_answer:answer})});
  return await r2.json();
}
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q)return; busy(true); LASTQ=q;
  const model=document.getElementById('model').value;
  try{
    let d;
    if(model==='local'){ d=await askLocal(q); }
    else{
      const r=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},
        body:JSON.stringify({question:q,model,context:ctx()})});
      d=await r.json();
    }
    if(d){ render(d);
      HIST=[q,...HIST.filter(x=>x!==q)].slice(0,30); localStorage.setItem('sb_hist',JSON.stringify(HIST)); drawHist();
      THREAD.push({q:q,a:LASTANS}); if(THREAD.length>8)THREAD=THREAD.slice(-8);
    }
  }catch(e){document.getElementById('out').innerHTML='<div class=card>error: '+esc(''+e)+'</div>'}
  busy(false);
}
function dictate(){
  const R=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!R){document.getElementById('ustat').textContent='voice input not supported in this browser';return;}
  const rec=new R();rec.lang='en-US';rec.interimResults=false;const b=document.getElementById('mic');
  b.classList.add('on');b.textContent='●';
  rec.onresult=e=>{const t=e.results[0][0].transcript;const q=document.getElementById('q');q.value=(q.value?q.value+' ':'')+t;};
  rec.onend=()=>{b.classList.remove('on');b.innerHTML='&#127908;';};rec.onerror=rec.onend;rec.start();
}
function speak(){const s=window.speechSynthesis;if(!s){document.getElementById('status').textContent='speech not supported in this browser';return;}
  if(s.speaking){s.cancel();return;} const u=new SpeechSynthesisUtterance(LASTANS||'');u.lang='en-US';u.rate=1;s.speak(u);}
function doUpload(){
  const inp=document.getElementById('file');const files=inp.files?[].slice.call(inp.files):[];
  const st=document.getElementById('ustat'); if(!files.length){st.textContent='choose a file first';return;}
  const total=files.length;let i=0;
  const next=()=>{
    if(i>=total){busy(false);if(total>1)st.textContent='reviewed '+total+' files';return;}
    const f=files[i],n=i+1;
    const textlike=/\.(txt|md|markdown|csv|tsv|json|log|py|js|html|xml|ya?ml)$/i.test(f.name);
    const fr=new FileReader();st.textContent='reading '+n+'/'+total+' · '+f.name+'…';
    fr.onload=async()=>{
      const body={filename:f.name,model:document.getElementById('model').value};
      if(textlike)body.text=fr.result; else body.b64=(''+fr.result).split(',')[1]||'';
      st.textContent='reviewing '+n+'/'+total+'…';busy(true);LASTQ='file: '+f.name;
      try{const r=await fetch('/upload',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
        const d=await r.json(); if(d.error){st.textContent='error: '+esc(d.error);}else{render(d);
          if(total===1)st.textContent=d.upload?('read '+d.upload.chars+' chars'+(d.upload.note?' · '+d.upload.note:'')):'done';}
      }catch(e){st.textContent='error'} i++; next();
    };
    if(textlike)fr.readAsText(f); else fr.readAsDataURL(f);
  };
  next();
}
function genImage(){
  const p=document.getElementById('q').value.trim();const st=document.getElementById('ustat');
  if(!p){st.textContent='type an image prompt in the box above first';return;}
  st.textContent='generating image…';busy(true);
  fetch('/generate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({prompt:p})})
   .then(r=>r.json()).then(d=>{
     if(d.error){st.textContent='error: '+esc(d.error);}
     else{const src=d.url||('data:image/png;base64,'+(d.b64||''));
       document.getElementById('out').innerHTML='<div class="card fade"><div class=k>Generated image</div>'+
         '<img src="'+src+'" alt="generated" style="max-width:100%;border-radius:12px">'+
         '<div class=muted style="margin-top:6px">'+esc(p)+'</div></div>';
       st.textContent='done';}
   }).catch(e=>{st.textContent='error'}).finally(()=>busy(false));
}
async function loadLibrary(){
  const st=document.getElementById('lstat');st.textContent='loading…';
  try{const d=await (await fetch('/library')).json();
    document.getElementById('lcount').textContent=d.count||0;
    document.getElementById('libfiles').innerHTML=(d.files||[]).map(f=>
      '<div class=repn><div class=h><span><b>'+esc(f.name)+'</b></span><span class=muted>'+f.chars+' chars</span></div>'+
      '<div class=e>'+esc(f.preview||'')+'</div></div>').join('')||'<span class=muted>no files yet — upload a file or feed the brain</span>';
    st.textContent='';
  }catch(e){st.textContent='error'}
}
function tally(arr){const m={};(arr||[]).forEach(x=>m[x]=(m[x]||0)+1);
  return Object.entries(m).map(([k,v])=>esc(k)+(v>1?' ×'+v:'')).join(', ')||'—';}
function confWhy(d){const o=d.output||{}; if((''+o.confidence).toLowerCase()!=='low')return '';
  const holds=(d.walk&&d.walk.holds)||[];
  if(holds.length)return 'Low because '+holds.length+' node'+(holds.length>1?'s':'')+' held — e.g. '+esc(holds[0].why)+' Clear it in the review queue to raise confidence.';
  return 'Low — doubt bit or an open gap; see the node walk below.';}
function walkRow(s){return '<div class=lane><span class="vd '+s.verdict+'">●</span> <b>'+esc(s.sb_id)+'</b> '+esc(s.sb_name)+' → '+esc(s.urr_id)+': <b>'+esc(s.verdict)+'</b>'+(s.memory_written?' <span class=memok>memory ✓</span>':'')+'<br><span class=muted style="margin-left:18px">'+esc(s.why)+'</span></div>';}
function walkCard(d){const w=d.walk; if(!w||!w.steps)return '';
  const holds=w.steps.filter(s=>s.verdict==='hold'), passes=w.steps.filter(s=>s.verdict!=='hold');
  // Holds are what need you — show them. Passes are folded so 70 'Clear' rows
  // don't bury the signal (open the details to see them all).
  const head=holds.length
    ?('<div class=muted style="margin-bottom:6px">Held — these need you:</div>'+holds.map(walkRow).join(''))
    :'<div class=lane><span class="vd pass">●</span> All '+w.node_count+' nodes cleared — no holds.</div>';
  const rest=passes.length
    ?('<details style="margin-top:8px"><summary>'+passes.length+' nodes passed (show all)</summary>'+passes.map(walkRow).join('')+'</details>'):'';
  return '<div class=card><div class=k>Node walk · SB ↔ URR <span class=num>'+w.node_count+' nodes · '+w.hold_count+' holds</span></div>'+head+rest+'</div>';}
function auditCard(d){const L=(d.output||{}).lanes||{}, a=L.audit; if(!a)return '';
  const row=(k,v)=>'<div class=lane><b>'+esc(k)+'</b> '+esc(v)+'</div>';
  let h=row('Document',(L.domain||{}).label||'numeric / financial');
  h+=row('Numeric cells read',a.number_count);
  if(a.candidate_total!=null)h+=row('Largest figure (likely grand total)',a.candidate_total);
  if((a.stated_totals||[]).length)h+=row('Near total / amount labels',a.stated_totals.join(', '));
  if((a.gst_figures||[]).length)h+=row('GST / tax figures',a.gst_figures.join(', '));
  h+=row('Negative / correction entries',a.negative_count+((a.negative_examples||[]).length?(' — e.g. '+a.negative_examples.join(', ')):''));
  if((a.caveats||[]).length)h+='<div class=fals>Cannot certify: '+a.caveats.map(esc).join(' · ')+'</div>';
  return '<div class=card><div class=k>Numeric audit <span class=num>computed, not guessed</span></div>'+h+'</div>';}
function reviewQueue(d){const h=(d.walk&&d.walk.holds)||[]; if(!h.length)return '';
  const cards=h.map(x=>{const a=x.ask||{};
    return '<div class=hold><div><b>'+esc(x.sb_id)+'</b> '+esc(x.name)+' <span class="badge warn">hold</span></div>'+
    '<div class=fivew><div><b>What</b>'+esc(a.what||x.why||'—')+'</div><div><b>Why</b>'+esc(a.why||'—')+'</div>'+
    '<div><b>How</b>'+esc(a.how||'—')+'</div><div><b>When</b>'+esc(a.when||'now')+'</div></div>'+
    ((a.options&&a.options.length)?'<div class=fivew style="margin-top:6px"><div style="grid-column:1/-1"><b>Options</b> '+a.options.map(o=>'<span class=tag>'+esc(o)+'</span>').join(' ')+'</div></div>':'')+
    '<textarea class=in id="hd_'+esc(x.sb_id)+'" placeholder="paste the data / source asked for, then Add data & re-run" style="min-height:46px"></textarea>'+
    '<div class=hactions><button class=btn onclick="review(\''+esc(x.sb_id)+'\',\'add_data\')">Add data &amp; re-run</button>'+
    '<button class=btn onclick="review(\''+esc(x.sb_id)+'\',\'reloop\')">Re-loop</button>'+
    '<button class=btn onclick="review(\''+esc(x.sb_id)+'\',\'approve\')">Approve</button></div></div>';}).join('');
  return '<div class=card><div class=k>Human review queue <span class=num>'+h.length+'</span></div>'+
    '<div class=muted style="margin-bottom:8px">Each held node tells you exactly what it needs. Add it, re-loop, or approve as-is.</div>'+cards+'</div>';}
async function review(id,action){
  const ta=document.getElementById('hd_'+id); const data=ta?ta.value.trim():'';
  const st=document.getElementById('out'); st.style.opacity=.5;
  try{const r=await fetch('/review',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({question:LASTQ,id,action,data,model:document.getElementById('model').value})});
    const d=await r.json(); if(d.resolved){st.style.opacity=1; return;} render(d);
  }catch(e){}; st.style.opacity=1;}
function render(d){
  LASTD=d; const o=d.output||{},lanes=o.lanes||{}; LASTANS=o.answer||'';
  const firedStages=new Set(),counts={};
  (d.trace||[]).forEach(t=>{const s=stageOf(t.node_id); if(s){firedStages.add(s); counts[s]=(counts[s]||0)+1;}});
  drawPyr(firedStages,counts);
  const m=(d.matched_examples||[]).map(x=>'<div class=lane>'+esc(x)+'</div>').join('')||'<span class=muted>none yet — feed your corpus</span>';
  const tr=(d.trace||[]).map(t=>{const h=t.halt?(' <span class=hl>[HALT:'+esc(t.halt)+']</span>'):'';
    return esc((t.node_id||'').padEnd(7))+' '+esc((t.action||'').padEnd(20))+' '+esc(t.status)+h+'  '+esc(t.note||'')}).join('<br>');
  document.getElementById('out').innerHTML=
    '<div class=fade>'+
    ((document.getElementById('cont').checked&&THREAD.length)?'<div class=card><div class=k>Conversation <span class=num>'+THREAD.length+'</span></div>'+THREAD.map(t=>'<div class=lane><b>You</b> '+esc(t.q)+'<br><span class=muted>'+esc((t.a||'').slice(0,240))+(t.a&&t.a.length>240?'…':'')+'</span></div>').join('')+'</div>':'')+
    (d.upload?'<div class=card><div class=k>File reviewed</div><div class=lane><b>'+esc(d.upload.filename)+'</b> · '+d.upload.chars+' chars'+(d.upload.note?' · <span class=hl>'+esc(d.upload.note)+'</span>':'')+'</div></div>':'')+
    '<div class=card><div class=k>Answer</div><div class=ans>'+esc(o.answer)+'</div>'+
      '<div class=meter><i style="width:'+confPct(o.confidence)+'%"></i></div>'+
      '<div class=badges><span class=badge>'+esc(o.classification)+'</span>'+
      '<span class=badge>evidence <b>'+esc(o.evidence_tag)+'</b></span>'+
      '<span class="badge '+confClass(o.confidence)+'">confidence <b>'+esc(o.confidence)+'</b></span>'+
      '<span class=badge>penetration <b>'+esc(o.penetration_score)+'</b></span>'+
      (confWhy(d)?'<div class=why>'+confWhy(d)+'</div>':'')+
      '<div class=fals>falsifier · '+esc(o.falsifier)+'</div>'+
      '<div class=hactions><button class="btn sm" onclick="speak()">🔊 Read aloud</button><button class="btn sm" onclick="downloadReport(\'md\')">⬇ Markdown</button><button class="btn sm" onclick="downloadReport(\'csv\')">⬇ CSV</button></div></div>'+
    auditCard(d)+walkCard(d)+reviewQueue(d)+
    '<div class=card><div class=k>Eternal example & wisdom match</div>'+m+'</div>'+
    '<div class=card><div class=k>Core Gate · human layer (SB-10)</div>'+
      '<div class=lane>dominant lens: <b>'+esc((lanes.human_layer||{}).dominant_lens||'—')+'</b></div>'+
      Object.entries((lanes.human_layer||{}).active||{}).map(([k,v])=>'<div class=lane><b>'+esc(k)+'</b> '+esc(v)+'</div>').join('')+'</div>'+
    '<div class=card><div class=k>Output lanes (URR-07)</div>'+
      '<div class=lane><b>Reality</b> '+esc(JSON.stringify(lanes.reality_path||{}))+'</div>'+
      (((lanes.wild_path||{}).preserved||[]).length?'<div class=lane><b>Wild path (preserved)</b> '+esc(JSON.stringify(lanes.wild_path.preserved))+'</div>':'')+
      '<div class=lane><b>Re-anchor</b> '+esc(lanes.reality_reanchor||'')+'</div>'+
      (lanes.safety?'<div class=lane><b class=hl>Safety</b> '+esc(JSON.stringify(lanes.safety))+'</div>':'')+'</div>'+
    '<div class=card><div class=k>Truth & evidence (Stages 3–6)</div>'+
      '<div class=lane><b>Doubt Engine</b> '+esc((lanes.doubt||{}).verdict||'—')+' · '+(((lanes.doubt||{}).fragilities)||[]).length+' fragilities</div>'+
      '<div class=lane><b>Witness</b> '+esc(((lanes.witness||[])[0])||'—')+'</div>'+
      '<div class=lane><b>Evidence ladder</b> '+tally((lanes.evidence_ledger||[]).map(e=>e.evidence_tag))+'</div>'+
      ((lanes.connections||[]).length?'<div class=lane><b>Dot-connections</b> '+esc((lanes.connections||[]).map(c=>c.ref+' ×'+c.appears_in).join(', '))+'</div>':'')+
      (lanes.merge_proposal?'<div class=lane><b class=hl>Merge proposed</b> '+esc((lanes.merge_proposal.contributing||[]).join(' + '))+' · needs human gate</div>':'')+
      (lanes.synthetic_fuel?'<div class=lane><b>Synthetic fuel</b> ['+esc(lanes.synthetic_fuel.stall)+'] '+esc(lanes.synthetic_fuel.fuel)+' <span class=tag>SYNTHETIC</span></div>':'')+'</div>'+
    (d.halts&&d.halts.length?'<div class=card><div class=k>Halts → loops opened</div><span class=hl>'+esc(d.halts.join(', '))+'</span></div>':'')+
    '<details><summary>engine trace ('+(d.trace||[]).length+' nodes) & memory</summary>'+
      '<div class=card><div class=trace>'+tr+'</div><div class=muted style="margin-top:10px">memory: '+
      esc(JSON.stringify(d.memory))+' · clone learns 1 example each run</div></div></details>'+
    '</div>';
}
function downloadReport(fmt){
  const d=LASTD; if(!d)return; const o=d.output||{}; let body,mime,ext;
  if(fmt==='csv'){
    const rows=[['field','value'],['question',LASTQ],['answer',(o.answer||'').replace(/\n/g,' ')],
      ['classification',o.classification],['evidence',o.evidence_tag],['confidence',o.confidence],
      ['penetration',o.penetration_score],['falsifier',o.falsifier]];
    ((d.walk&&d.walk.steps)||[]).forEach(s=>rows.push(['node '+s.sb_id,s.verdict+' — '+s.why]));
    body=rows.map(r=>r.map(c=>'"'+(''+(c==null?'':c)).replace(/"/g,'""')+'"').join(',')).join('\n');
    mime='text/csv';ext='csv';
  }else{
    let md='# Sourceborn report\n\n**Ask:** '+LASTQ+'\n\n## Answer\n\n'+(o.answer||'')+'\n\n';
    md+='- classification: '+o.classification+'\n- evidence: '+o.evidence_tag+'\n- confidence: '+o.confidence+'\n- penetration: '+o.penetration_score+'\n\n**Falsifier:** '+o.falsifier+'\n\n## Node walk\n\n';
    ((d.walk&&d.walk.steps)||[]).forEach(s=>md+='- **'+s.sb_id+'** '+s.sb_name+' → '+s.verdict+' — '+s.why+'\n');
    body=md;mime='text/markdown';ext='md';
  }
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([body],{type:mime}));
  a.download='sourceborn-report.'+ext;a.click();
}
async function loadReport(){
  const st=document.getElementById('repstat');st.textContent='loading…';
  try{const d=await (await fetch('/memory/report')).json();renderReport(d,'Memory report (live)');st.textContent='';}
  catch(e){st.textContent='error'}
}
function renderReport(rep,title){
  const nodes=(rep.nodes||[]).map(n=>'<div class=repn><div class=h><span><b>'+esc(n.id)+'</b> '+esc(n.name)+'</span><span class=muted>'+n.entry_count+' entries</span></div>'+
    (n.recent||[]).map(e=>'<div class=e>'+esc(e.content)+(e.tags&&e.tags.length?' <span class=muted>['+esc(e.tags.join(', '))+']</span>':'')+'</div>').join('')+'</div>').join('');
  document.getElementById('out').innerHTML='<div class="card fade"><div class=k>'+esc(title)+
    ' <span class=num>'+((rep.totals||{}).total_memory_entries||0)+' entries · '+((rep.totals||{}).nodes_with_brains||0)+' nodes</span></div>'+
    '<div class=muted style="margin-bottom:8px">'+esc(rep.at||'')+'</div><div class=rep>'+(nodes||'<span class=muted>nothing stored yet</span>')+'</div></div>';
}
async function saveSnapshot(){
  const st=document.getElementById('repstat');st.textContent='saving…';
  try{await fetch('/snapshot',{method:'POST',headers:{'content-type':'application/json'},body:'{}'});
    st.textContent='snapshot saved'; loadSnapshots();}catch(e){st.textContent='error'}
}
async function loadSnapshots(){
  try{const list=await (await fetch('/snapshots')).json();
    document.getElementById('snaps').innerHTML=list.length?('<div class=k style="margin-top:8px">Snapshots</div>'+
      list.map(s=>'<a class="hist" style="cursor:pointer" onclick="showSnap(\''+esc(s.id)+'\')">'+esc(s.name)+' · '+((s.total||{}).total_memory_entries||0)+'</a>').join('')):'';
  }catch(e){}
}
async function showSnap(id){
  try{const d=await (await fetch('/snapshot?id='+encodeURIComponent(id))).json();renderReport(d,'Snapshot · '+(d.name||id));}catch(e){}
}
async function feed(){
  const text=document.getElementById('ftext').value.trim(); if(!text)return;
  const name=document.getElementById('fname').value.trim()||'note';
  const fstat=document.getElementById('fstat'); fstat.textContent='adding…';
  try{
    const r=await fetch('/ingest',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name,text})});
    const d=await r.json();
    fstat.textContent='memory: '+((d.memory&&d.memory.total_memory_entries)||0)+' · clone: '+(d.examples||0);
    document.getElementById('ftext').value=''; document.getElementById('fname').value='';
  }catch(e){fstat.textContent='error'}
}
async function loadBrains(){
  try{
    const d=await (await fetch('/brains')).json(); let total=0,html='';
    for(const [g,list] of Object.entries(d)){
      total+=list.length;
      html+='<details><summary>'+esc(g)+' ('+list.length+')</summary>';
      for(const c of list){
        const flags=[c.human_review?'human-gate':'',c.urr_gate?'URR-gate':'',c.gen_params?'+params':'','risk:'+c.risk,c.write].filter(Boolean).join(' · ');
        html+='<div class=lane style="cursor:pointer" onclick="brainDetail(\''+c.id+'\')"><b>'+esc(c.id)+'</b> '+esc(c.name)+'<br><span class=muted style=font-size:11px>'+esc(flags)+'</span></div>';
      }
      html+='</details>';
    }
    document.getElementById('brains').innerHTML=html; document.getElementById('bcount').textContent=total;
  }catch(e){}
}
function _sel(name,opts,val){return '<select id=bs_'+name+'>'+opts.map(o=>'<option'+(o===val?' selected':'')+'>'+o+'</option>').join('')+'</select>'}
function _chk(name,val){return '<label class=switch><input type=checkbox id=bs_'+name+(val?' checked':'')+'><span class=track></span> '+name.replace(/_/g,' ')+'</label>'}
async function brainDetail(id){
  const d=await (await fetch('/brain?id='+encodeURIComponent(id))).json(); const c=d.config; if(!c)return;
  document.getElementById('out').innerHTML='<div class="card fade"><div class=k>Brain '+esc(c.node_id)+' — '+esc(c.name)+'</div>'+
    '<div class=lane>kind: '+esc(c.kind)+' · stage: '+c.stage+' · pyramid (Node→Main→Sub→Micro): '+esc(JSON.stringify(c.pyramid))+'</div>'+
    '<div class=lane>role: '+esc(c.role)+'</div>'+
    '<div class=bset>risk '+_sel('risk_level',['low','medium','high'],c.risk_level)+
      ' &nbsp; write '+_sel('write_policy',['every_visit','on_finding','checkpoint'],c.write_policy)+'</div>'+
    '<div class=bset>'+_chk('urr_gate',c.urr_gate)+_chk('human_review',c.human_review)+_chk('weekly_update',c.weekly_update)+_chk('can_generate_parameters',c.can_generate_parameters)+'</div>'+
    '<div class=toolbar style="border:0;padding:0"><button class=btn onclick="saveBrain(\''+c.node_id+'\')">Save settings</button><span class=status id=savestat></span>'+
      (c.immutable_source?'<span class=tag>immutable source</span>':'')+'</div>'+
    '<div class="lane muted">tracks: '+esc((c.tracked_groups||[]).join(', '))+' · memory entries: '+((d.memory&&d.memory.entry_count)||0)+'</div></div>';
}
async function saveBrain(id){
  const g=n=>document.getElementById('bs_'+n), st=document.getElementById('savestat'); st.textContent='saving…';
  const body={id,risk_level:g('risk_level').value,write_policy:g('write_policy').value,
    urr_gate:g('urr_gate').checked,human_review:g('human_review').checked,
    weekly_update:g('weekly_update').checked,can_generate_parameters:g('can_generate_parameters').checked};
  try{const d=await (await fetch('/brain/settings',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})).json();
    st.textContent=d.ok?'saved ✓':'error'; loadBrains();}catch(e){st.textContent='error'}
}
async function weeklyUpdate(){
  const b=document.getElementById('bstat'); b.textContent='updating…';
  try{const d=await (await fetch('/brains/update',{method:'POST',headers:{'content-type':'application/json'},body:'{}'})).json();
    b.textContent='updated '+d.updated+'/'+d.total;}catch(e){b.textContent='error'}
}
loadBrains(); loadSnapshots();
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))ask()});
</script></div>
<script type="module">
// On-device inference: the model runs in THIS browser on the user's GPU via
// WebGPU. The prompt never goes to a third-party LLM — only back to this app's
// own engine for SB+URR framing. Library + weights are fetched once (then cached
// by the browser) from the WebLLM CDN.
import { CreateMLCEngine } from "https://esm.run/@mlc-ai/web-llm";
let engine=null, loading=null;
const DEF="Llama-3.2-1B-Instruct-q4f16_1-MLC";
function mid(){ try{ return localStorage.getItem('sb_local_model')||DEF; }catch(e){ return DEF; } }
async function load(onp){
  if(engine && engine.__mid===mid()) return engine;     // reuse unless model changed
  loading = CreateMLCEngine(mid(), { initProgressCallback: p=>{ try{ onp&&onp(p); }catch(e){} } });
  engine = await loading; engine.__mid = mid(); loading=null; return engine;
}
async function generate(system, prompt){
  const e = await load();
  const reply = await e.chat.completions.create({
    messages:[{role:'system',content:system||''},{role:'user',content:prompt||''}],
    temperature:0.7, max_tokens:1024 });
  return (reply && reply.choices && reply.choices[0] && reply.choices[0].message.content) || '';
}
window.__localLLM = { load, generate, supported:()=>!!navigator.gpu };
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        route = urlparse(self.path)
        path, qs = route.path, parse_qs(route.query)
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/health":
            body = json.dumps({"ok": True, "model": ENGINE.model.name,
                               "models": model_status(),
                               "brains": len(ENGINE.brains.all()),
                               "weekly": scheduler.status(SB_ROOT)})
            self._send(200, body.encode(), "application/json")
        elif path == "/diag":          # tiny connectivity self-test for one model
            name = (qs.get("model") or ["openrouter"])[0]
            m = get_model(name)
            reply = m.complete("connectivity test", "Reply with the single word: ok")
            self._send(200, json.dumps({"requested": name, "model": m.name,
                                        "reply": reply[:400]}).encode(), "application/json")
        elif path == "/memory/report":
            self._send(200, json.dumps(_memory_report()).encode(), "application/json")
        elif path == "/library":
            self._send(200, json.dumps(_library()).encode(), "application/json")
        elif path == "/snapshots":
            self._send(200, json.dumps(_list_snapshots()).encode(), "application/json")
        elif path == "/snapshot":
            sid = re.sub(r"[^0-9A-Za-z]", "", (qs.get("id") or [""])[0])
            fp = os.path.join(SNAP_DIR, sid + ".json")
            if not sid or not os.path.exists(fp):
                self._send(404, b'{"error":"no such snapshot"}', "application/json")
                return
            with open(fp, encoding="utf-8") as f:
                self._send(200, f.read().encode(), "application/json")
        elif path == "/brains":
            payload = {g: [{
                "id": c.node_id, "name": c.name, "kind": c.kind, "stage": c.stage,
                "human_review": c.human_review, "urr_gate": c.urr_gate,
                "risk": c.risk_level, "write": c.write_policy,
                "weekly": c.weekly_update, "gen_params": c.can_generate_parameters,
                "groups": c.tracked_groups,
            } for c in cs] for g, cs in ENGINE.brains.by_stage().items()}
            self._send(200, json.dumps(payload).encode(), "application/json")
        elif path == "/brain":
            node_id = (qs.get("id") or [""])[0]
            cfg = ENGINE.brains.get(node_id)
            if not cfg:
                self._send(404, b'{"error":"no such node"}', "application/json")
                return
            body = json.dumps({"config": asdict(cfg),
                               "memory": ENGINE.memory.brain(node_id).meta})
            self._send(200, body.encode(), "application/json")
        elif path == "/graph":
            from .nodes import SB_NODES, URR_NODES
            sb = [n.sb_id for n in SB_NODES]
            nodes = ([{"id": n.sb_id, "kind": "SB", "stage": n.stage, "name": n.name}
                      for n in SB_NODES]
                     + [{"id": n.urr_id, "kind": "URR", "name": n.name} for n in URR_NODES])
            edges = [{"from": sb[i], "to": sb[i + 1]} for i in range(len(sb) - 1)]
            gates = [c.node_id for c in ENGINE.brains.all()
                     if c.kind == "SB" and c.urr_gate]
            self._send(200, json.dumps({
                "nodes": nodes, "edges": edges, "urr_gates": gates,
                "note": "full interconnection — any node may feed-forward to any "
                        "earlier node (Principle 8)"}).encode(), "application/json")
        else:
            self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self) -> None:
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self._send(400, b'{"error":"bad json"}', "application/json")
            return
        if self.path == "/ingest":
            text = (data.get("text") or "").strip()
            if not text:
                self._send(400, b'{"error":"empty text"}', "application/json")
                return
            stats = _ingest_text((data.get("name") or "note").strip(), text)
            self._send(200, json.dumps({"ok": True, **stats}).encode(), "application/json")
            return
        if self.path == "/snapshot":
            self._send(200, json.dumps(_save_snapshot(data.get("name", ""))).encode(),
                       "application/json")
            return
        if self.path == "/upload":
            self._upload(data)
            return
        if self.path == "/brains/update":
            self._send(200, json.dumps(ENGINE.brains.weekly_update()).encode(),
                       "application/json")
            return
        if self.path == "/brain/settings":
            node_id = (data.get("id") or "").strip()
            try:
                cfg = ENGINE.brains.update(
                    node_id, **{k: v for k, v in data.items() if k != "id"})
            except KeyError:
                self._send(404, b'{"error":"no such node"}', "application/json")
                return
            self._send(200, json.dumps({"ok": True, "config": asdict(cfg)}).encode(),
                       "application/json")
            return
        if self.path == "/review":
            self._review(data)
            return
        if self.path == "/generate":
            prompt = (data.get("prompt") or "").strip()
            if not prompt:
                self._send(400, b'{"error":"empty prompt"}', "application/json")
                return
            self._send(200, json.dumps(generate_image(prompt)).encode(), "application/json")
            return
        if self.path != "/ask":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        try:
            question = (data.get("question") or "").strip()
            if not question:
                self._send(400, b'{"error":"empty question"}', "application/json")
                return
            context = (data.get("context") or "").strip()
            if context:                      # same-chat continuation (thread)
                question = (question +
                            "\n\n[continuing our thread — your prior answer]:\n"
                            + context)
            name = str(data.get("model", "offline") or "offline").lower()
            if name == "local":              # on-device lane (browser GPU)
                self._ask_local(question, data)
                return
            model = get_model(name)
            walk = ENGINE.run_walk(question, model=model)
            self._send(200, self._walk_payload(walk["result"], walk, model.name),
                       "application/json")
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")

    # -- shared payload + actions -----------------------------------------
    @staticmethod
    def _walk_payload(res, walk, model_name: str, extra: dict | None = None) -> bytes:
        payload = {
            "output": asdict(res.output),
            "micro_questions": res.micro_questions,
            "matched_examples": res.matched_examples,
            "trace": [asdict(t) for t in res.trace],
            "halts": res.halts,
            "memory": ENGINE.memory.stats(),
            "model": model_name,
            "walk": walk["walk"],
        }
        if extra:
            payload.update(extra)
        return json.dumps(payload).encode()

    def _upload(self, data: dict) -> None:
        """Phase 1: review an uploaded file. Extract text (stdlib), run the
        SB<->URR walk over it, and fold it into the brain."""
        filename = (data.get("filename") or "upload").strip()
        img_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
        if data.get("b64") and filename.lower().endswith(img_exts):
            model = get_model(data.get("model", "offline"))
            low = filename.lower()
            mime = ("image/jpeg" if low.endswith((".jpg", ".jpeg")) else
                    "image/webp" if low.endswith(".webp") else
                    "image/gif" if low.endswith(".gif") else "image/png")
            seen = model.complete_vision(
                "You are a precise visual analyst in the user's voice.",
                f"Review the image '{filename}': what it shows, key details, and "
                "anything notable or worth flagging.", data["b64"], mime)
            _ingest_text(filename, f"[image '{filename}' seen]:\n{seen}")
            walk = ENGINE.run_walk(
                f"Review this uploaded image '{filename}':\n\n{seen}", model=model)
            self._send(200, self._walk_payload(
                walk["result"], walk, model.name,
                {"upload": {"filename": filename, "chars": len(seen),
                            "note": "vision review"}}), "application/json")
            return
        text = data.get("text")
        if text is None and data.get("b64"):
            try:
                text, note = extract_text(filename, base64.b64decode(data["b64"]))
            except Exception as exc:
                self._send(400, json.dumps({"error": f"decode failed: {exc}"}).encode(),
                           "application/json")
                return
        else:
            text, note = (text or ""), ""
        text = (text or "").strip()
        if not text:
            self._send(200, json.dumps({"error": note or "no text found in file"}).encode(),
                       "application/json")
            return
        _ingest_text(filename, text)                 # compounds the brain
        model = get_model(data.get("model", "offline"))
        ask = f"Review this uploaded file '{filename}' and respond:\n\n{text}"
        walk = ENGINE.run_walk(ask, model=model)
        self._send(200, self._walk_payload(
            walk["result"], walk, model.name,
            {"upload": {"filename": filename, "chars": len(text), "note": note}}),
            "application/json")

    def _review(self, data: dict) -> None:
        """Human review queue: approve / add data / re-loop a held node."""
        question = (data.get("question") or "").strip()
        action = (data.get("action") or "").strip()
        node_id = (data.get("id") or "").strip()
        extra = (data.get("data") or "").strip()
        if action == "approve":
            ENGINE.memory.master_log({"event": "human_approve", "node": node_id})
            self._send(200, json.dumps({"ok": True, "resolved": node_id}).encode(),
                       "application/json")
            return
        if not question:
            self._send(400, b'{"error":"need question to re-loop"}', "application/json")
            return
        model = get_model(data.get("model", "offline"))
        if action == "add_data" and extra:
            _ingest_text(f"review-{node_id or 'note'}", extra)
            walk = ENGINE.run_walk(question, model=model, live_override=extra)
        else:
            walk = ENGINE.run_walk(question, model=model, live_override=extra or None)
        self._send(200, self._walk_payload(walk["result"], walk, model.name),
                   "application/json")

    def _ask_local(self, question: str, data: dict) -> None:
        """On-device (browser-GPU) lane — two phases, so the prompt never reaches
        a third-party LLM. Phase 1: run the engine just far enough to build its
        real output prompt and hand that back to the browser. Phase 2: the
        browser returns the GPU-generated draft and the FULL SB + URR walk frames
        it. ``live_override=NO_LIVE`` keeps the private lane from phoning out
        (no Tavily), and is identical across both phases so the prompt is stable."""
        local_answer = data.get("local_answer")
        if local_answer is None:                       # phase 1 — capture prompt
            try:
                ENGINE.run_walk(question, model=CaptureModel(), live_override=NO_LIVE)
            except LocalCaptured as cap:
                self._send(200, json.dumps({
                    "stage": "need_local",
                    "system": cap.system, "prompt": cap.prompt}).encode(),
                    "application/json")
                return
            # The engine never reached the model (rare) — give the browser a sane
            # fallback so the lane still answers.
            voice = ""
            try:
                voice = ENGINE.persona.voice_guidance()
            except Exception:
                pass
            self._send(200, json.dumps({
                "stage": "need_local", "system": voice, "prompt": question}).encode(),
                "application/json")
            return
        # phase 2 — frame the on-device draft through the full walk
        walk = ENGINE.run_walk(question, model=LocalBridgeModel(str(local_answer)),
                               live_override=NO_LIVE)
        self._send(200, self._walk_payload(walk["result"], walk, "local"),
                   "application/json")


def _maybe_ingest_on_boot() -> None:
    """Deploy-time corpus load: if SB_INGEST_CORPUS points at a folder and the
    brain is empty, ingest it once (e.g. a Render disk mounted with your cores)."""
    folder = os.environ.get("SB_INGEST_CORPUS")
    if folder and os.path.isdir(folder) and \
            ENGINE.memory.stats().get("total_memory_entries", 0) == 0:
        from .ingest import ingest_folder
        stats = ingest_folder(folder, root=os.environ.get("SB_ROOT", ".sourceborn"))
        print(f"ingested corpus on boot: {stats}")


def main() -> None:
    _maybe_ingest_on_boot()
    scheduler.start_weekly_scheduler(ENGINE, SB_ROOT)  # auto Monday brain update
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Sourceborn web service on http://0.0.0.0:{port}  (model: {ENGINE.model.name})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
