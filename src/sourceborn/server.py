"""Sourceborn web service — a zero-dependency HTTP server (stdlib only).

Runs the engine behind a small dark chat UI and a JSON API, so it can be
deployed to Render (or any host) with nothing to install but Python.

    python -m sourceborn.server          # local: http://localhost:8000
    PORT=10000 python -m sourceborn.server

Endpoints:
    GET  /            -> the chat UI
    POST /ask         -> {"question": "...", "public": false} -> engine result JSON
    GET  /health      -> {"ok": true}

Set ANTHROPIC_API_KEY (env var on Render) to swap the offline stub for Claude.
Note: Render's disk is ephemeral; for persistent memory mount a Render Disk at
``.sourceborn`` or move memory to a DB (see docs/RECOMMENDATION.md, Phase 3).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import SourcebornEngine

ENGINE = SourcebornEngine(root=os.environ.get("SB_ROOT", ".sourceborn"))

PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Sourceborn</title><style>
:root{--bg:#0b0d12;--panel:#141821;--line:#232a36;--ink:#e7ecf3;--mut:#8a93a6;--acc:#6ea8fe}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:880px;margin:0 auto;padding:28px 18px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}
textarea{width:100%;background:#0d1017;border:1px solid var(--line);color:var(--ink);
border-radius:10px;padding:12px;font:inherit;min-height:78px;resize:vertical}
.row{display:flex;gap:12px;align-items:center;margin-top:10px;flex-wrap:wrap}
button{background:var(--acc);color:#06101f;border:0;border-radius:10px;padding:10px 18px;
font-weight:600;cursor:pointer}button:disabled{opacity:.5}
label{color:var(--mut);font-size:13px;display:flex;gap:6px;align-items:center}
.tag{display:inline-block;background:#0d1017;border:1px solid var(--line);border-radius:999px;
padding:2px 10px;margin:3px 4px 0 0;font-size:12px;color:var(--mut)}
.ans{white-space:pre-wrap}.k{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.lane{border-left:2px solid var(--line);padding:4px 0 4px 12px;margin:8px 0}
.trace{font:12px/1.7 ui-monospace,Menlo,monospace;color:var(--mut)}
.hl{color:#ffb454}.gd{color:#7ee787}.muted{color:var(--mut)}details{margin-top:8px}
summary{cursor:pointer;color:var(--mut)}
</style></head><body><div class=wrap>
<h1>Sourceborn</h1>
<div class=sub>eternal example, present fact &middot; more parameters, more outcome &mdash; model: <b id=model>...</b></div>
<div class=card>
  <textarea id=q placeholder="Ask anything — a question, a mess, a half-thought…"></textarea>
  <div class=row>
    <button id=go onclick=ask()>Run engine</button>
    <label><input type=checkbox id=pub> public-safe answer</label>
    <span class=muted id=status></span>
  </div>
</div>
<div id=out></div>
<script>
fetch('/health').then(r=>r.json()).then(d=>{document.getElementById('model').textContent=d.model})
async function ask(){
  const q=document.getElementById('q').value.trim(); if(!q)return;
  const go=document.getElementById('go'); go.disabled=true;
  document.getElementById('status').textContent='running SB + URR…';
  const r=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({question:q,public:document.getElementById('pub').checked})});
  const d=await r.json(); go.disabled=false; document.getElementById('status').textContent='';
  render(d);
}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function render(d){
  const o=d.output, lanes=o.lanes||{};
  let m=(d.matched_examples||[]).map(x=>'<div class=lane>'+esc(x)+'</div>').join('')||'<span class=muted>none yet — feed your corpus</span>';
  let tr=(d.trace||[]).map(t=>{let h=t.halt?(' <span class=hl>[HALT:'+esc(t.halt)+']</span>'):'';
    return esc(t.node_id.padEnd(7))+' '+esc((t.action||'').padEnd(22))+' '+esc(t.status)+h+'  '+esc(t.note||'')}).join('<br>');
  let html='<div class=card><div class=k>Answer</div><div class=ans>'+esc(o.answer)+'</div>'+
    '<div class=row><span class=tag>'+esc(o.classification)+'</span><span class=tag>evidence: '+esc(o.evidence_tag)+
    '</span><span class=tag>confidence: '+esc(o.confidence)+'</span><span class=tag>penetration: '+esc(o.penetration_score)+
    '</span>'+(o.public_safe?'<span class=tag>public-safe</span>':'')+'</div>'+
    '<div class=muted style="margin-top:8px">falsifier: '+esc(o.falsifier)+'</div></div>'+
    '<div class=card><div class=k>Eternal example &amp; wisdom match</div>'+m+'</div>'+
    '<div class=card><div class=k>Output lanes (URR-07)</div>'+
      '<div class=lane><b>Reality</b> '+esc(JSON.stringify(lanes.reality_path||{}))+'</div>'+
      '<div class=lane><b>Wild path (preserved)</b> '+esc(JSON.stringify((lanes.wild_path||{}).preserved||[]))+'</div>'+
      '<div class=lane><b>Re-anchor</b> '+esc(lanes.reality_reanchor||'')+'</div>'+
      (lanes.safety?'<div class=lane><b class=hl>Safety</b> '+esc(JSON.stringify(lanes.safety))+'</div>':'')+
    '</div>'+
    (d.halts&&d.halts.length?'<div class=card><div class=k>Halts → loops opened</div><span class=hl>'+esc(d.halts.join(', '))+'</span></div>':'')+
    '<details><summary>engine trace ('+(d.trace||[]).length+' nodes) &amp; memory</summary>'+
      '<div class=card trace><div class=trace>'+tr+'</div><div class=muted style="margin-top:10px">memory: '+
      esc(JSON.stringify(d.memory))+' &middot; clone learns 1 example each run</div></div></details>';
  document.getElementById('out').innerHTML=html;
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))ask()})
</script></div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # quiet logs
        pass

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/health":
            body = json.dumps({"ok": True, "model": ENGINE.model.__class__.__name__})
            self._send(200, body.encode(), "application/json")
        else:
            self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self) -> None:
        if self.path != "/ask":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            question = (data.get("question") or "").strip()
            if not question:
                self._send(400, b'{"error":"empty question"}', "application/json")
                return
            res = ENGINE.run(question, public_safe=bool(data.get("public")))
            payload = {
                "output": asdict(res.output),
                "micro_questions": res.micro_questions,
                "matched_examples": res.matched_examples,
                "trace": [asdict(t) for t in res.trace],
                "halts": res.halts,
                "memory": ENGINE.memory.stats(),
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
        except Exception as exc:  # never crash the server on a bad ask
            self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Sourceborn web service on http://0.0.0.0:{port}  "
          f"(model: {ENGINE.model.__class__.__name__})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
