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
:root{--bg:#0a0c11;--panel:#141821;--p2:#0d1017;--line:#232a36;--ink:#e7ecf3;--mut:#8a93a6;--acc:#6ea8fe;--hl:#ffb454;--gd:#7ee787}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#16203a 0,var(--bg) 60%);
color:var(--ink);font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:26px 18px;display:grid;grid-template-columns:1fr 280px;gap:18px}
@media(max-width:820px){.wrap{grid-template-columns:1fr}}
header{grid-column:1/-1}h1{font-size:21px;margin:0}.sub{color:var(--mut);font-size:13px;margin:2px 0 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 14px}
textarea{width:100%;background:var(--p2);border:1px solid var(--line);color:var(--ink);border-radius:10px;
padding:12px;font:inherit;min-height:80px;resize:vertical}
.row{display:flex;gap:12px;align-items:center;margin-top:10px;flex-wrap:wrap}
button{background:var(--acc);color:#06101f;border:0;border-radius:10px;padding:10px 18px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5}select,label{background:var(--p2);color:var(--ink);border:1px solid var(--line);
border-radius:8px;padding:7px 9px;font:inherit}label{display:flex;gap:7px;align-items:center;color:var(--mut)}
label input{accent-color:var(--acc)}.muted{color:var(--mut)}.k{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
.tag{display:inline-block;background:var(--p2);border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:3px 4px 0 0;font-size:12px;color:var(--mut)}
.ans{white-space:pre-wrap}.lane{border-left:2px solid var(--line);padding:3px 0 3px 12px;margin:7px 0}
.trace{font:12px/1.7 ui-monospace,Menlo,monospace;color:var(--mut)}.hl{color:var(--hl)}.gd{color:var(--gd)}
.pyr{display:flex;flex-direction:column;gap:5px}.stg{display:flex;justify-content:space-between;border:1px solid var(--line);
border-radius:8px;padding:6px 10px;font-size:12px;background:var(--p2)}.stg.on{border-color:var(--acc);color:var(--ink)}
.stg b{color:var(--mut);font-weight:600}.stg.on b{color:var(--acc)}
.plvl{margin:3px auto;border:1px solid var(--line);background:var(--p2);border-radius:8px;padding:5px 8px;text-align:center;font-size:11px;color:var(--mut);transition:.2s}
.plvl.on{border-color:var(--acc);background:#16203a;color:var(--ink)}
.bset{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:8px 0}
.bset select{padding:5px 7px}
.mem{display:flex;gap:6px;flex-wrap:wrap}.dot{font-size:12px;border:1px solid var(--line);border-radius:999px;padding:2px 9px;color:var(--mut)}
.hist a{display:block;color:var(--mut);font-size:13px;padding:5px 0;border-bottom:1px solid var(--line);cursor:pointer;text-decoration:none}
.hist a:hover{color:var(--ink)}details summary{cursor:pointer;color:var(--mut)}
</style></head><body><div class=wrap>
<header><h1>Sourceborn</h1><div class=sub>eternal example, present fact &middot; more parameters, more outcome</div></header>

<main>
  <div class=card>
    <textarea id=q placeholder="Ask anything — a question, a mess, a half-thought…  (Cmd/Ctrl+Enter to run)"></textarea>
    <div class=row>
      <button id=go onclick=ask()>Run engine</button>
      <select id=model title="base model"></select>
      <label><input type=checkbox id=pub> public-safe</label>
      <span class=muted id=status></span>
    </div>
  </div>
  <div id=out></div>
</main>

<aside>
  <div class=card><div class=k>Three memories</div>
    <div class=mem><span class=dot>reflex · corpus</span><span class=dot>instinct · wisdom</span><span class=dot>eyes · live fact</span></div>
  </div>
  <div class=card><div class=k>Engine pyramid (stages fired)</div><div class=pyr id=pyr></div></div>
  <div class=card><div class=k>History</div><div class=hist id=hist><span class=muted>empty</span></div></div>
  <div class=card><div class=k>Feed the brain</div>
    <input id=fname placeholder="name (optional)" style="width:100%;background:var(--p2);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:7px;margin-bottom:6px;font:inherit">
    <textarea id=ftext placeholder="paste a note, thought, or core…" style="min-height:58px"></textarea>
    <div class=row><button onclick=feed()>Add to memory</button><span class=muted id=fstat></span></div>
  </div>
  <div class=card><div class=k>Node brains (<span id=bcount>0</span>)</div>
    <div class=row><button onclick=weeklyUpdate() style="padding:7px 12px">Weekly update</button><span class=muted id=bstat></span></div>
    <div id=brains style="margin-top:8px"></div>
  </div>
</aside>

<script>
const STAGES=[["1","Foundation & Intake"],["2","Human Core"],["3","Truth & Doubt"],["4","Evidence"],
["5","Connection & Memory"],["6","Synthetic & Invention"],["7","Risk & Control"],["8","Output & Update"]];
function stageOf(id){let n=parseInt((id||'').replace('SB-',''));if(!n)return 0;
  return n<=8?1:n<=18?2:n<=28?3:n<=36?4:n<=44?5:n<=52?6:n<=60?7:8}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
let HIST=JSON.parse(localStorage.getItem('sb_hist')||'[]');

fetch('/health').then(r=>r.json()).then(d=>{
  const sel=document.getElementById('model');
  const labels={offline:'Offline (no key)',claude:'Claude (deep)',grok:'Grok (raw)',openai:'OpenAI'};
  for(const [k,ok] of Object.entries(d.models)){
    const o=document.createElement('option');o.value=k;
    o.textContent=labels[k]+(ok?'':' — add key');if(!ok&&k!=='offline')o.disabled=true;
    if(k===d.model)o.selected=true;sel.appendChild(o);
  }
}); drawPyr(new Set(),{}); drawHist();

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
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q)return;
  const go=document.getElementById('go'); go.disabled=true;
  document.getElementById('status').textContent='running SB + URR…';
  try{
    const r=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({question:q,public:document.getElementById('pub').checked,model:document.getElementById('model').value})});
    const d=await r.json(); render(d);
    HIST=[q,...HIST.filter(x=>x!==q)].slice(0,30); localStorage.setItem('sb_hist',JSON.stringify(HIST)); drawHist();
  }catch(e){document.getElementById('out').innerHTML='<div class=card>error: '+esc(''+e)+'</div>'}
  go.disabled=false; document.getElementById('status').textContent='';
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
    '<div class=card><div class=k>Answer</div><div class=ans>'+esc(o.answer)+'</div>'+
      '<div class=row><span class=tag>'+esc(o.classification)+'</span><span class=tag>evidence: '+esc(o.evidence_tag)+
      '</span><span class=tag>confidence: '+esc(o.confidence)+'</span><span class=tag>penetration: '+esc(o.penetration_score)+
      '</span>'+(o.public_safe?'<span class=tag>public-safe</span>':'')+'</div>'+
      '<div class=muted style="margin-top:8px">falsifier: '+esc(o.falsifier)+'</div></div>'+
    '<div class=card><div class=k>Eternal example & wisdom match</div>'+m+'</div>'+
    '<div class=card><div class=k>Core Gate · human layer (SB-10)</div>'+
      '<div class=lane>dominant lens: <b>'+esc((lanes.human_layer||{}).dominant_lens||'—')+'</b></div>'+
      Object.entries((lanes.human_layer||{}).active||{}).map(([k,v])=>'<div class=lane><b>'+esc(k)+'</b> '+esc(v)+'</div>').join('')+'</div>'+
    '<div class=card><div class=k>Output lanes (URR-07)</div>'+
      '<div class=lane><b>Reality</b> '+esc(JSON.stringify(lanes.reality_path||{}))+'</div>'+
      '<div class=lane><b>Wild path (preserved)</b> '+esc(JSON.stringify((lanes.wild_path||{}).preserved||[]))+'</div>'+
      '<div class=lane><b>Re-anchor</b> '+esc(lanes.reality_reanchor||'')+'</div>'+
      (lanes.safety?'<div class=lane><b class=hl>Safety</b> '+esc(JSON.stringify(lanes.safety))+'</div>':'')+'</div>'+
    (d.halts&&d.halts.length?'<div class=card><div class=k>Halts → loops opened</div><span class=hl>'+esc(d.halts.join(', '))+'</span></div>':'')+
    '<details><summary>engine trace ('+(d.trace||[]).length+' nodes) & memory</summary>'+
      '<div class=card><div class=trace>'+tr+'</div><div class=muted style="margin-top:10px">memory: '+
      esc(JSON.stringify(d.memory))+' · clone learns 1 example each run</div></div></details>';
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
function _chk(name,val){return '<label><input type=checkbox id=bs_'+name+(val?' checked':'')+'> '+name.replace(/_/g,' ')+'</label>'}
async function brainDetail(id){
  const d=await (await fetch('/brain?id='+encodeURIComponent(id))).json(); const c=d.config; if(!c)return;
  document.getElementById('out').innerHTML='<div class=card><div class=k>Brain '+esc(c.node_id)+' — '+esc(c.name)+'</div>'+
    '<div class=lane>kind: '+esc(c.kind)+' · stage: '+c.stage+' · pyramid (Node→Main→Sub→Micro): '+esc(JSON.stringify(c.pyramid))+'</div>'+
    '<div class=lane>role: '+esc(c.role)+'</div>'+
    '<div class=bset>risk '+_sel('risk_level',['low','medium','high'],c.risk_level)+
      ' &nbsp; write '+_sel('write_policy',['every_visit','on_finding','checkpoint'],c.write_policy)+'</div>'+
    '<div class=bset>'+_chk('urr_gate',c.urr_gate)+_chk('human_review',c.human_review)+_chk('weekly_update',c.weekly_update)+_chk('can_generate_parameters',c.can_generate_parameters)+'</div>'+
    '<div class=row><button onclick="saveBrain(\''+c.node_id+'\')">Save settings</button><span class=muted id=savestat></span>'+
      (c.immutable_source?'<span class=tag>immutable source</span>':'')+'</div>'+
    '<div class=lane class=muted>tracks: '+esc((c.tracked_groups||[]).join(', '))+' · memory entries: '+((d.memory&&d.memory.entry_count)||0)+'</div></div>';
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
            res = ENGINE.run(question, public_safe=bool(data.get("public")), model=model)
            payload = {
                "output": asdict(res.output),
                "micro_questions": res.micro_questions,
                "matched_examples": res.matched_examples,
                "trace": [asdict(t) for t in res.trace],
                "halts": res.halts,
                "memory": ENGINE.memory.stats(),
                "model": model.name,
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
