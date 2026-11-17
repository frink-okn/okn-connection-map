"""Offline step: an interactive connection explorer for one run (runs/<label>/explorer.html).

Pick a source graph and see every graph it reaches: by which identifier scheme, how many shared
identifiers, which connector graph adds reach, and whether MCP-OKN's catalog knows the connection.
Pick a target as well and it lists candidate paths (up to 3 hops) ranked by their weakest hop:
the first, visible form of the path planner.

Self-contained HTML, no network access needed to open it.
"""
from __future__ import annotations

import json

from .common import read_json

GEO = {"ZIP5", "county_FIPS", "state_FIPS", "S2_L13", "NAICS"}
CONNECTORS = {"ubergraph", "babel", "wikidata", "identifier-mappings", "okn-void"}


def _domain(schemes: dict) -> str:
    if not schemes:
        return "unknown"
    geo = sum(n for s, n in schemes.items() if s in GEO)
    return "geography" if geo * 2 >= sum(schemes.values()) else "biomedical"


def build_data(run_dir):
    mp = read_json(run_dir / "map.json")
    cmp = read_json(run_dir / "comparison.json")
    prof = read_json(run_dir / "profile.json", {}) or {}
    st = read_json(run_dir / "keysets_state.json", {}) or {}
    plan = read_json(run_dir / "plan.json", {}) or {}
    pg = prof.get("graphs", {})
    eps_by_graph = {}
    for e in plan.get("endpoints", []):
        s = st.get("endpoints", {}).get(e["id"], {}).get("status", "not_run")
        eps_by_graph.setdefault(e["graph"], {}).setdefault(s, 0)
        eps_by_graph[e["graph"]][s] += 1
    graphs = {}
    for g in sorted(set(mp["graphs"]) | set(eps_by_graph)):
        info = mp["graphs"].get(g, {"keys": 0, "schemes": {}})
        p = pg.get(g, {}) or {}
        graphs[g] = {"keys": info["keys"], "schemes": info["schemes"], "domain": _domain(info["schemes"]),
                     "connector": g in CONNECTORS, "release": p.get("kgf_version"),
                     "endpoints": eps_by_graph.get(g, {})}
    conns = []
    for c in cmp["connections"]:
        conns.append({"a": c["a"], "b": c["b"], "direct": c["direct"], "via": c["via"], "reach": c["reach"],
                      "label": c["label"], "tool": c.get("tool_status"), "catalog": c.get("catalog_ids", [])})
    return {"label": run_dir.name, "at": st.get("at") or prof.get("at"), "headline": cmp["headline"],
            "graphs": graphs, "connections": conns, "connectors": mp.get("connectors", {}),
            "meter": st.get("meter_total")}


def run(run_dir):
    data = build_data(run_dir)
    html = PAGE.replace("/*DATA*/null", json.dumps(data, separators=(",", ":")))
    out = run_dir / "explorer.html"
    out.write_text(html, encoding="utf-8")
    return out


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OKN Connection Explorer</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1b1d21;--quiet:#5d6470;--line:#e2e4e8;--accent:#1F6FB2;--accent-soft:#e3eef8;
--new:#1F6FB2;--confirmed:#6b7280;--refused:#C00000;--refused-soft:#fbe9e9;--bar:#9db9d6;--bridge:#d79b2b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15171b;--panel:#1d2026;--ink:#e8eaee;--quiet:#9aa1ad;--line:#2e333b;
--accent:#6aa8e0;--accent-soft:#1d2c3b;--new:#6aa8e0;--confirmed:#8b929c;--refused:#ff6b6b;--refused-soft:#3a1f22;--bar:#3f6d99;--bridge:#e0b04f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:18px 24px 10px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{font-size:19px;margin:0 0 2px}.sub{color:var(--quiet);font-size:12.5px}
.tiles{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.tile{border:1px solid var(--line);border-radius:8px;padding:6px 12px;min-width:120px}
.tile b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.tile span{font-size:11.5px;color:var(--quiet)}
main{display:grid;grid-template-columns:260px 1fr;gap:0;min-height:calc(100vh - 140px)}
aside{border-right:1px solid var(--line);background:var(--panel);padding:12px;overflow:auto;max-height:calc(100vh - 140px)}
aside input{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink);margin-bottom:8px}
.grp{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--quiet);margin:12px 4px 4px}
.g{display:flex;justify-content:space-between;padding:5px 8px;border-radius:6px;cursor:pointer}
.g:hover{background:var(--accent-soft)}.g.sel{background:var(--accent);color:#fff}.g.sel small{color:#fff}
.g small{color:var(--quiet);font-variant-numeric:tabular-nums}
section{padding:16px 22px;overflow:auto}
.row{display:grid;grid-template-columns:160px 1fr 210px;gap:12px;align-items:center;padding:7px 8px;border-radius:6px;cursor:pointer;border:1px solid transparent}
.row:hover{border-color:var(--line);background:var(--panel)}.row.sel{border-color:var(--accent);background:var(--panel)}
.bar{height:14px;display:flex;border-radius:3px;overflow:hidden;background:var(--line)}
.bar i{display:block;height:100%}.bar .d{background:var(--bar)}.bar .v{background:var(--bridge)}
.num{font-size:12px;color:var(--quiet);font-variant-numeric:tabular-nums}
.badge{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;border:1px solid}
.b-confirmed{color:var(--confirmed);border-color:var(--confirmed)}.b-new{color:var(--new);border-color:var(--new)}
.b-contradicts_refusal{color:var(--refused);border-color:var(--refused);background:var(--refused-soft)}
h2{font-size:15px;margin:4px 0 8px}h3{font-size:13.5px;margin:18px 0 6px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--quiet);margin-bottom:10px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.cols{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:10px}
.path{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:13px}
.path .n{font-weight:600}.path .e{font-size:11.5px;color:var(--quiet);border:1px dashed var(--line);border-radius:4px;padding:1px 6px}
.path .e.miss{border-color:var(--refused);color:var(--refused)}
.muted{color:var(--quiet)}table{border-collapse:collapse;width:100%;font-size:12.5px}td,th{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line)}
th{color:var(--quiet);font-weight:500}td.r{text-align:right;font-variant-numeric:tabular-nums}
svg text{fill:var(--ink)}
@media (max-width:820px){main{grid-template-columns:1fr}aside{max-height:none;border-right:0;border-bottom:1px solid var(--line)}.cols{grid-template-columns:1fr}.row{grid-template-columns:110px 1fr}.row .num:last-child{grid-column:1/-1}}
</style></head><body>
<header><h1>OKN Connection Explorer</h1><div class="sub" id="sub"></div><div class="tiles" id="tiles"></div></header>
<main><aside><input id="q" placeholder="Filter graphs…" aria-label="Filter graphs"><div id="list"></div></aside>
<section id="view"><p class="muted">Pick a source graph on the left.</p></section></main>
<script>
const D=/*DATA*/null;
const $=s=>document.querySelector(s),fmt=n=>(n||0).toLocaleString();
const LABEL={confirmed:"in catalog",new:"missing from catalog",contradicts_refusal:"catalog says no join"};
let src=null,dst=null;
// adjacency over non-connector graphs; weight = identifiers a hop can carry
const adj={};
for(const c of D.connections){
  const d=Object.values(c.direct).reduce((a,b)=>a+b,0),v=Math.max(0,...Object.values(c.via));
  const e={a:c.a,b:c.b,direct:d,via:v,schemes:c.direct,connectors:c.via,label:c.label,c};
  (adj[c.a]=adj[c.a]||[]).push({to:c.b,...e});(adj[c.b]=adj[c.b]||[]).push({to:c.a,...e});
}
function hdr(){
  const h=D.headline;$("#sub").textContent=`Run “${D.label}” · computed ${D.at?D.at.slice(0,16).replace("T"," "):""} UTC · read-only against FRINK federated SPARQL, KGF and okn-void`;
  const t=[[h.graphs_profiled,"graphs with key sets"],[h.connections_total,"graph pairs that share identifiers"],[h.connections_confirmed,"already in MCP-OKN catalog"],[h.connections_new,"missing from catalog"],[h.connections_contradicting_refusals,"catalog says no join"],[`${h.catalog_reproduced}/${h.catalog_testable}`,"stored crosswalks reproduced"]];
  $("#tiles").innerHTML=t.map(([n,s])=>`<div class="tile"><b>${typeof n==="number"?fmt(n):n}</b><span>${s}</span></div>`).join("");
}
function list(){
  const q=$("#q").value.toLowerCase(),gs=Object.entries(D.graphs).filter(([g])=>g.includes(q));
  const groups={biomedical:[],geography:[],connector:[],unknown:[]};
  for(const [g,i] of gs)groups[i.connector?"connector":i.domain].push([g,i]);
  const name={biomedical:"Biomedical",geography:"Geography",connector:"Connector graphs",unknown:"No key sets"};
  $("#list").innerHTML=Object.entries(groups).filter(([,v])=>v.length).map(([k,v])=>`<div class="grp">${name[k]}</div>`+
    v.map(([g,i])=>`<div class="g${g===src?" sel":""}" data-g="${g}"><span>${g}</span><small>${(adj[g]||[]).length} links</small></div>`).join("")).join("");
  document.querySelectorAll(".g").forEach(el=>el.onclick=()=>{src=el.dataset.g;dst=null;list();view();});
}
function paths(s,t,maxHops=3,k=8){
  const out=[];
  (function walk(node,seen,hops){
    if(hops.length>maxHops)return;
    if(node===t&&hops.length){out.push(hops.slice());return;}
    for(const e of adj[node]||[]){if(seen.has(e.to)||D.graphs[e.to]?.connector)continue;
      seen.add(e.to);hops.push(e);walk(e.to,seen,hops);hops.pop();seen.delete(e.to);}
  })(s,new Set([s]),[]);
  const cap=e=>Math.max(e.direct,e.via);
  out.forEach(p=>{p.bottleneck=Math.min(...p.map(cap));p.missing=p.filter(e=>e.label!=="confirmed").length;});
  out.sort((x,y)=>x.length-y.length||y.bottleneck-x.bottleneck);
  return out.slice(0,k);
}
function ego(s,rows){
  const W=520,H=300,cx=W/2,cy=H/2,R=115,n=rows.length;if(!n)return"";
  const mx=Math.max(...rows.map(r=>r.direct+r.extra),1);
  let el=`<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Graphs connected to ${s}">`;
  rows.forEach((r,i)=>{const a=-Math.PI/2+2*Math.PI*i/n,x=cx+R*Math.cos(a),y=cy+R*Math.sin(a);
    const col=r.label==="contradicts_refusal"?"var(--refused)":r.label==="new"?"var(--new)":"var(--confirmed)";
    const w=1+4*Math.log1p(r.direct+r.extra)/Math.log1p(mx);
    el+=`<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="${col}" stroke-width="${w.toFixed(1)}" ${r.direct?"":'stroke-dasharray="5 4"'} opacity=".85"/>`;
    const lx=cx+(R+14)*Math.cos(a),anchor=Math.cos(a)>.2?"start":Math.cos(a)<-.2?"end":"middle";
    el+=`<circle cx="${x}" cy="${y}" r="4" fill="${col}"/><text x="${lx}" y="${cy+(R+14)*Math.sin(a)+4}" font-size="10.5" text-anchor="${anchor}">${r.to}</text>`;});
  el+=`<circle cx="${cx}" cy="${cy}" r="30" fill="var(--accent)"/><text x="${cx}" y="${cy+4}" font-size="11" text-anchor="middle" style="fill:#fff">${s.length>12?s.slice(0,11)+"…":s}</text></svg>`;
  return el;
}
function view(){
  if(!src)return;const g=D.graphs[src];
  const rows=(adj[src]||[]).map(e=>{const r=e.c.reach[src]||{};return{...e,extra:r.only_via_connector||0,reachDirect:r.direct??e.direct};})
    .sort((x,y)=>(y.direct+y.extra)-(x.direct+x.extra));
  const mx=Math.max(...rows.map(r=>r.direct+r.extra),1);
  const sch=Object.entries(g.schemes).sort((a,b)=>b[1]-a[1]).map(([s,n])=>`${s} ${fmt(n)}`).join(" · ")||"none";
  const eps=Object.entries(g.endpoints).map(([s,n])=>`${n} ${s.replace("_"," ")}`).join(", ");
  let h=`<h2>${src}</h2><div class="muted" style="font-size:12.5px">${fmt(g.keys)} canonical identifiers (${sch})${g.release?` · release ${g.release}`:""}${eps?` · endpoints: ${eps}`:""}</div>`;
  if(!rows.length){$("#view").innerHTML=h+`<p class="muted">No shared identifiers with another graph in this run.</p>`;return;}
  h+=`<div class="cols"><div><h3>Reaches ${rows.length} graphs</h3><div class="legend"><span><i style="background:var(--bar)"></i>shared directly</span><span><i style="background:var(--bridge)"></i>added only through a connector graph</span></div>`;
  h+=rows.map(r=>`<div class="row${r.to===dst?" sel":""}" data-t="${r.to}"><span>${r.to}</span>
    <div class="bar" title="${fmt(r.direct)} shared directly, ${fmt(r.extra)} more via connectors"><i class="d" style="width:${100*r.direct/mx}%"></i><i class="v" style="width:${100*r.extra/mx}%"></i></div>
    <span class="num">${fmt(r.direct)}${r.extra?` + ${fmt(r.extra)}`:""} · <span class="badge b-${r.label}">${LABEL[r.label]}</span></span></div>`).join("");
  h+=`</div><div><h3>Neighbourhood</h3>${ego(src,rows.slice(0,24))}<div class="legend"><span><i style="background:var(--confirmed)"></i>in catalog</span><span><i style="background:var(--new)"></i>missing</span><span><i style="background:var(--refused)"></i>catalog says no join</span><span>dashed = connector only</span></div><div id="detail"></div></div></div>`;
  $("#view").innerHTML=h;
  document.querySelectorAll(".row").forEach(el=>el.onclick=()=>{dst=el.dataset.t;view();});
  if(dst)detail(rows.find(r=>r.to===dst));
}
function detail(r){
  if(!r)return;const c=r.c;
  let h=`<h3>${src} → ${dst}</h3><div class="card"><table><tr><th>How they connect</th><th class="r">identifiers</th></tr>`;
  for(const [s,n] of Object.entries(c.direct))h+=`<tr><td>${s==="LABEL"?"same name (label match)":"same "+s+" identifier"}</td><td class="r">${fmt(n)}</td></tr>`;
  for(const [k,n] of Object.entries(c.via))h+=`<tr><td>mapped through <b>${k}</b></td><td class="r">${fmt(n)}</td></tr>`;
  const rr=c.reach[src];if(rr)h+=`<tr><td>${src} identifiers reaching ${dst}: directly / either way</td><td class="r">${fmt(rr.direct)} / ${fmt(rr.either)}</td></tr>`;
  h+=`</table><p style="margin:8px 0 0;font-size:12.5px"><span class="badge b-${c.label}">${LABEL[c.label]}</span> ${c.catalog.length?`stored crosswalks: ${c.catalog.join(", ")}`:c.tool==="known_non_join"?"MCP-OKN lists this pair as a known non-join.":"No stored crosswalk in MCP-OKN."}</p></div>`;
  const ps=paths(src,dst);
  h+=`<h3>Candidate paths (up to 3 hops)</h3><p class="muted" style="font-size:12px;margin:0 0 6px">Shortest first, then by the weakest hop. A one-hop count is exact; for longer paths the weakest hop is an upper bound on what the path can carry, since each hop may share different identifiers. Hops not in the MCP-OKN catalog are outlined in red.</p>`;
  h+=ps.map((p,i)=>{let s=`<div class="card"><div class="path"><span class="n">${src}</span>`;
    for(const e of p){const how=Object.keys(e.schemes).join("/")||("via "+Object.keys(e.connectors).join("/"));
      s+=`<span class="e${e.label==="confirmed"?"":" miss"}">${how} · ${fmt(Math.max(e.direct,e.via))}</span><span class="n">${e.to}</span>`;}
    return s+`</div><div class="muted" style="font-size:12px;margin-top:4px">${p.length} hop${p.length>1?"s":""} · ${p.length>1?"at most ":""}${fmt(p.bottleneck)} identifiers · ${p.missing} hop${p.missing===1?"":"s"} missing from catalog</div></div>`;}).join("")||`<p class="muted">No path within 3 hops.</p>`;
  $("#detail").innerHTML=h;
}
$("#q").oninput=list;hdr();list();
</script></body></html>
"""
