"""Sourceborn web service — a zero-dependency HTTP server (stdlib only).

Runs the engine behind a dark chat dashboard and a JSON API, so it can be
deployed to Render (or any host) with nothing to install but Python.

    python -m sourceborn.server          # local: http://localhost:8000
    PORT=10000 python -m sourceborn.server

Endpoints:
    GET  /            -> the dashboard UI
    POST /ask         -> {"question","public","model"} -> engine result JSON
    GET  /health      -> {"ok",true,"model",..,"models",{claude:bool,...}}

Set ANTHROPIC_API_KEY / XAI_API_KEY / OPENAI_API_KEY (env vars on Render) to turn
on real reasoning. Render's disk is ephemeral; for persistent memory mount a
Render Disk at ``.sourceborn`` or use a DB (docs/RECOMMENDATION.md, Phase 3).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import scheduler
from .engine import SourcebornEngine
from .llm import get_model, model_status

SB_ROOT = os.environ.get("SB_ROOT", ".sourceborn")
ENGINE = SourcebornEngine(root=SB_ROOT)


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
.app{max-width:1180px;margin:0 auto;padding:0 18px 60px}
.topbar{position:sticky;top:0;z-index:20;display:flex;justify-content:space-between;align-items:center;gap:12px;
 padding:14px 4px;margin-bottom:8px;flex-wrap:wrap;
 backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
 background:linear-gradient(180deg,rgba(7,8,9,.86),rgba(7,8,9,.35));border-bottom:1px solid var(--line)}
.brand{display:flex;gap:12px;align-items:center}
.logo{width:38px;height:38px;border-radius:11px;background:var(--grad);display:grid;place-items:center;
 box-shadow:0 6px 18px -6px rgba(124,139,255,.6)}
.brand .name{font-size:18px;font-weight:700;letter-spacing:-.01em}
.brand .tag{font-size:12px;color:var(--mut)}
.stats{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{display:inline-flex;gap:7px;align-items:center;background:var(--panel);border:1px solid var(--line);
 border-radius:999px;padding:6px 12px;font-size:12.5px;color:var(--mut)}
.pill b{color:var(--ink);font-weight:600}
.pdot{width:8px;height:8px;border-radius:50%;background:var(--mut2)}
.pdot.live{background:var(--ok);box-shadow:0 0 0 3px rgba(52,211,153,.18)}
.grid{display:grid;grid-template-columns:1fr 320px;gap:18px;align-items:start}
@media(max-width:880px){.grid{grid-template-columns:1fr}}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
 border-radius:16px;padding:18px;margin:0 0 16px;box-shadow:var(--shadow);transition:border-color .15s}
.card:hover{border-color:var(--line2)}aside .card{padding:15px}
.k{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);
 margin:0 0 11px;display:flex;align-items:center;gap:8px}.k .num{margin-left:auto;color:var(--mut2)}
.hero{padding:6px;background:linear-gradient(180deg,var(--elev),var(--panel2));border-color:var(--line2)}
.hero .inner{background:var(--panel2);border:1px solid var(--line);border-radius:13px;padding:14px}
textarea,input,select{font:inherit;color:var(--ink)}
#q{width:100%;background:transparent;border:0;color:var(--ink);min-height:84px;resize:vertical;outline:none;font-size:16px;line-height:1.5}
#q::placeholder{color:var(--mut2)}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px;padding-top:12px;border-top:1px solid var(--line)}
.field{display:inline-flex;gap:7px;align-items:center;background:var(--panel);border:1px solid var(--line);
 border-radius:10px;padding:0 10px;height:38px;color:var(--mut);font-size:13px}
.field select,.field input{background:transparent;border:0;outline:none;color:var(--ink);font-size:13px}
.field input[type=number]{width:40px}.field:focus-within{border-color:var(--acc);box-shadow:var(--ring)}
button.primary{height:38px;padding:0 18px;border:0;border-radius:10px;background:var(--grad);color:#0a0f1f;
 font-weight:700;font-size:14px;cursor:pointer;display:inline-flex;gap:8px;align-items:center;
 box-shadow:0 8px 20px -8px rgba(124,139,255,.7);transition:.15s}
button.primary:hover{filter:brightness(1.08);transform:translateY(-1px)}
button.primary:disabled{opacity:.6;cursor:default;transform:none}
.btn{height:34px;padding:0 13px;border:1px solid var(--line2);border-radius:9px;background:var(--panel);
 color:var(--ink);font-weight:600;font-size:13px;cursor:pointer;transition:.15s}
.btn:hover{border-color:var(--acc);color:#fff}
.switch{display:inline-flex;gap:9px;align-items:center;cursor:pointer;color:var(--mut);font-size:13px;user-select:none}
.switch input{display:none}
.switch .track{width:38px;height:22px;border-radius:999px;background:var(--line2);position:relative;transition:.18s}
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
    <div class=logo><svg width=22 height=22 viewBox="0 0 24 24"><path d="M12 2 22 21 2 21Z" fill="#0a0f1f" opacity=".9"/><path d="M7.5 12.5h9M9.5 17h5" stroke="#fff" stroke-width="1.4" opacity=".55" stroke-linecap=round/></svg></div>
    <div><div class=name>Sourceborn</div><div class=tag>eternal example &middot; present fact &middot; more parameters, more outcome</div></div>
  </div>
  <div class=stats>
    <span class=pill id=mpill><span class=pdot id=pdot></span> <b id=mname>offline</b></span>
    <span class=pill>brains <b id=bpill>95</b></span>
    <span class=pill id=wpill>weekly <b>&mdash;</b></span>
  </div>
</header>

<div class=grid>
<main>
  <section class="card hero">
    <div class=inner>
      <textarea id=q placeholder="Ask anything — a question, a mess, a half-thought…   ⌘/Ctrl + Enter to run"></textarea>
      <div class=toolbar>
        <button id=go class=primary onclick=ask()><span id=goico>&#9654;</span><span id=golbl>Run engine</span></button>
        <span class=field><select id=model title="base model"></select></span>
        <span class=field title="RGL: compound over N loops">loops <input type=number id=loops value=1 min=1 max=6></span>
        <label class=switch><input type=checkbox id=pub><span class=track></span> public-safe</label>
        <span class=status id=status></span>
      </div>
    </div>
    <div class=chips id=examples></div>
  </section>
  <div id=out></div>
</main>

<aside>
  <div class=card><div class=k>Three memories</div>
    <div class=mem>
      <div class=memrow><span class="md r"></span><div><b>Reflex</b> &middot; your corpus &amp; clone</div></div>
      <div class=memrow><span class="md i"></span><div><b>Instinct</b> &middot; wisdom bank</div></div>
      <div class=memrow><span class="md e"></span><div><b>Eyes</b> &middot; live fact</div></div>
    </div></div>
  <div class=card><div class=k>Engine pyramid <span class=num>stages fired</span></div><div class=pyr id=pyr></div></div>
  <div class=card><div class=k>History</div><div class=hist id=hist><span class=muted>empty</span></div></div>
  <div class=card><div class=k>Feed the brain</div>
    <input id=fname class=in placeholder="name (optional)" style="margin-bottom:7px">
    <textarea id=ftext class=in placeholder="paste a note, thought, or core…" style="min-height:60px;resize:vertical"></textarea>
    <div class=toolbar style="border:0;padding:0;margin-top:9px"><button class=btn onclick=feed()>Add to memory</button><span class=status id=fstat></span></div>
  </div>
  <div class=card><div class=k>Node brains <span class=num id=bcount>0</span></div>
    <div class=toolbar style="border:0;padding:0;margin-bottom:4px"><button class=btn onclick=weeklyUpdate()>Weekly update</button><span class=status id=bstat></span></div>
    <div id=brains style="margin-top:6px"></div>
  </div>
</aside>
</div>

<script>
const STAGES=[["1","Foundation & Intake"],["2","Human Core"],["3","Truth & Doubt"],["4","Evidence"],
["5","Connection & Memory"],["6","Synthetic & Invention"],["7","Risk & Control"],["8","Output & Update"]];
const EXAMPLES=["Why does the small idea win? Prove it with current data.",
"Should I scale my small business or do an MBA?","I want to prove myself and I fear failing",
"Connect my last three ideas into one move"];
function stageOf(id){let n=parseInt((id||'').replace('SB-',''));if(!n)return 0;
  return n<=8?1:n<=18?2:n<=28?3:n<=36?4:n<=44?5:n<=52?6:n<=60?7:8}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function confClass(c){c=(''+c).toLowerCase();return c=='high'?'ok':c=='medium'?'warn':c=='low'?'bad':''}
function confPct(c){c=(''+c).toLowerCase();return c=='high'?92:c=='medium'?62:c=='low'?32:50}
let HIST=JSON.parse(localStorage.getItem('sb_hist')||'[]');

fetch('/health').then(r=>r.json()).then(d=>{
  const sel=document.getElementById('model');
  const labels={offline:'Offline (no key)',claude:'Claude (deep)',grok:'Grok (raw)',openai:'OpenAI'};
  for(const [k,ok] of Object.entries(d.models)){
    const o=document.createElement('option');o.value=k;
    o.textContent=labels[k]+(ok?'':' — add key');if(!ok&&k!=='offline')o.disabled=true;
    if(k===d.model)o.selected=true;sel.appendChild(o);
  }
  document.getElementById('mname').textContent=(labels[d.model]||d.model).split(' ')[0];
  if(d.model!=='offline')document.getElementById('pdot').classList.add('live');
  document.getElementById('bpill').textContent=d.brains||95;
  const set=d.weekly&&d.weekly.last_weekly_update;
  document.getElementById('wpill').innerHTML='weekly <b>'+(set?'active':'due')+'</b>';
}); drawPyr(new Set(),{}); drawHist();
document.getElementById('examples').innerHTML=EXAMPLES.map(e=>'<span class=chip>'+esc(e)+'</span>').join('');
document.querySelectorAll('#examples .chip').forEach((c,i)=>c.onclick=()=>{
  const q=document.getElementById('q');q.value=EXAMPLES[i];q.focus()});

function drawPyr(firedStages,counts){
  firedStages=firedStages||new Set(); counts=counts||{};
  let html='';
  for(let i=STAGES.length-1;i>=0;i--){            // apex (stage 8) on top -> base
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
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q)return; busy(true);
  try{
    const r=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({question:q,public:document.getElementById('pub').checked,model:document.getElementById('model').value,loops:+document.getElementById('loops').value})});
    const d=await r.json(); render(d);
    HIST=[q,...HIST.filter(x=>x!==q)].slice(0,30); localStorage.setItem('sb_hist',JSON.stringify(HIST)); drawHist();
  }catch(e){document.getElementById('out').innerHTML='<div class=card>error: '+esc(''+e)+'</div>'}
  busy(false);
}
function render(d){
  const o=d.output||{},lanes=o.lanes||{};
  const firedStages=new Set(),counts={};
  (d.trace||[]).forEach(t=>{const s=stageOf(t.node_id); if(s){firedStages.add(s); counts[s]=(counts[s]||0)+1;}});
  drawPyr(firedStages,counts);
  const m=(d.matched_examples||[]).map(x=>'<div class=lane>'+esc(x)+'</div>').join('')||'<span class=muted>none yet — feed your corpus</span>';
  const tr=(d.trace||[]).map(t=>{const h=t.halt?(' <span class=hl>[HALT:'+esc(t.halt)+']</span>'):'';
    return esc((t.node_id||'').padEnd(7))+' '+esc((t.action||'').padEnd(20))+' '+esc(t.status)+h+'  '+esc(t.note||'')}).join('<br>');
  document.getElementById('out').innerHTML=
    '<div class=fade>'+
    (d.recursion?('<div class=card><div class=k>RGL · '+d.recursion.loop_count+' loops'+(d.recursion.converged?' · converged':'')+'</div>'+(d.recursion.history||[]).map(h=>'<div class=lane>loop '+h.loop+' · '+esc(h.confidence)+'/'+esc(h.penetration)+' · '+esc((h.answer||'').slice(0,90))+'</div>').join('')+'</div>'):'')+
    '<div class=card><div class=k>Answer</div><div class=ans>'+esc(o.answer)+'</div>'+
      '<div class=meter><i style="width:'+confPct(o.confidence)+'%"></i></div>'+
      '<div class=badges><span class=badge>'+esc(o.classification)+'</span>'+
      '<span class=badge>evidence <b>'+esc(o.evidence_tag)+'</b></span>'+
      '<span class="badge '+confClass(o.confidence)+'">confidence <b>'+esc(o.confidence)+'</b></span>'+
      '<span class=badge>penetration <b>'+esc(o.penetration_score)+'</b></span>'+
      (o.public_safe?'<span class=badge>public-safe</span>':'')+'</div>'+
      '<div class=fals>falsifier · '+esc(o.falsifier)+'</div></div>'+
    '<div class=card><div class=k>Eternal example & wisdom match</div>'+m+'</div>'+
    '<div class=card><div class=k>Core Gate · human layer (SB-10)</div>'+
      '<div class=lane>dominant lens: <b>'+esc((lanes.human_layer||{}).dominant_lens||'—')+'</b></div>'+
      Object.entries((lanes.human_layer||{}).active||{}).map(([k,v])=>'<div class=lane><b>'+esc(k)+'</b> '+esc(v)+'</div>').join('')+'</div>'+
    '<div class=card><div class=k>Output lanes (URR-07)</div>'+
      '<div class=lane><b>Reality</b> '+esc(JSON.stringify(lanes.reality_path||{}))+'</div>'+
      '<div class=lane><b>Wild path (preserved)</b> '+esc(JSON.stringify((lanes.wild_path||{}).preserved||[]))+'</div>'+
      '<div class=lane><b>Re-anchor</b> '+esc(lanes.reality_reanchor||'')+'</div>'+
      (lanes.safety?'<div class=lane><b class=hl>Safety</b> '+esc(JSON.stringify(lanes.safety))+'</div>':'')+'</div>'+
    '<div class=card><div class=k>Truth & evidence (Stages 3–6)</div>'+
      '<div class=lane><b>Doubt Engine</b> '+esc((lanes.doubt||{}).verdict||'—')+' · '+(((lanes.doubt||{}).fragilities)||[]).length+' fragilities</div>'+
      '<div class=lane><b>Witness</b> '+esc(((lanes.witness||[])[0])||'—')+'</div>'+
      '<div class=lane><b>Evidence ladder</b> '+esc(((lanes.evidence_ledger||[]).map(e=>e.evidence_tag).join(', '))||'—')+'</div>'+
      ((lanes.connections||[]).length?'<div class=lane><b>Dot-connections</b> '+esc((lanes.connections||[]).map(c=>c.ref+' ×'+c.appears_in).join(', '))+'</div>':'')+
      (lanes.merge_proposal?'<div class=lane><b class=hl>Merge proposed</b> '+esc((lanes.merge_proposal.contributing||[]).join(' + '))+' · needs human gate</div>':'')+
      (lanes.synthetic_fuel?'<div class=lane><b>Synthetic fuel</b> ['+esc(lanes.synthetic_fuel.stall)+'] '+esc(lanes.synthetic_fuel.fuel)+' <span class=tag>SYNTHETIC</span></div>':'')+'</div>'+
    (d.halts&&d.halts.length?'<div class=card><div class=k>Halts → loops opened</div><span class=hl>'+esc(d.halts.join(', '))+'</span></div>':'')+
    '<details><summary>engine trace ('+(d.trace||[]).length+' nodes) & memory</summary>'+
      '<div class=card><div class=trace>'+tr+'</div><div class=muted style="margin-top:10px">memory: '+
      esc(JSON.stringify(d.memory))+' · clone learns 1 example each run</div></div></details>'+
    '</div>';
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
loadBrains();
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))ask()});
</script></div></body></html>"""


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
        elif path == "/brains":
            # settings of every node brain, grouped by stage
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
        if self.path == "/brains/update":   # weekly brain update (Principle 12)
            self._send(200, json.dumps(ENGINE.brains.weekly_update()).encode(),
                       "application/json")
            return
        if self.path == "/brain/settings":  # edit one node brain's settings
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
        if self.path != "/ask":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        try:
            question = (data.get("question") or "").strip()
            if not question:
                self._send(400, b'{"error":"empty question"}', "application/json")
                return
            model = get_model(data.get("model", "offline"))
            loops = max(1, min(int(data.get("loops", 1) or 1), 6))
            recursion = None
            if loops > 1:                       # RGL: compound over N loops
                rec = ENGINE.run_recursive(question, loops=loops, model=model)
                res, recursion = rec["result"], rec["recursion"]
            else:
                res = ENGINE.run(question, public_safe=bool(data.get("public")), model=model)
            payload = {
                "output": asdict(res.output),
                "micro_questions": res.micro_questions,
                "matched_examples": res.matched_examples,
                "trace": [asdict(t) for t in res.trace],
                "halts": res.halts,
                "memory": ENGINE.memory.stats(),
                "model": model.name,
                "recursion": recursion,
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")


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
