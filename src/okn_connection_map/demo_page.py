"""Offline: one self-contained page for showing find_join_paths (runs/<label>/join_paths_demo.html).

  python demo_page.py [--label 2026-10-15c]

Sections: the evidence in numbers; pick any two graphs and see MCP-OKN's get_join_strategy
answer today beside the computed answer; agreement with the catalog's own verified counts;
how it plugs into MCP-OKN; limits.
"""
from __future__ import annotations

import argparse
import collections
import json

from . import join_paths
from . import config, strategy
from .common import read_json

SHOWCASE = [("nde", "rdkg"), ("scales", "sudokn"), ("geoconnex", "ruralkg"), ("nde", "prokn"),
            ("biobricks-aopwiki", "biobricks-ice"), ("biobricks-tox21", "sawgraph"), ("spoke-okn", "nde")]


def agreement(m):
    """Stored crosswalks the map reproduces: does the computed count match the catalog's own?"""
    rows = []
    for e in m.cmp["catalog"]:
        if e["status"] != "reproduced" or e.get("bridge_kg"):
            continue
        comp, key = e.get("computed_direct") or {}, (e.get("shared_key") or "")
        v = next((n for s, n in comp.items() if s.lower() in key.lower() or key.lower() in s.lower()), None)
        if v is None and len(comp) == 1:
            v = next(iter(comp.values()))
        ref = e.get("live_oct") if e.get("live_oct") is not None else e.get("stored")
        if v is None or not isinstance(ref, (int, float)) or not ref:
            continue
        cls = "exact" if v == ref else ("within 5%" if abs(v / ref - 1) <= 0.05 else "differs")
        rows.append({"id": e["id"], "pair": f"{e['a']} × {e['b']}", "key": key, "catalog": ref,
                     "computed": v, "class": cls})
    return rows


def build(label=None):
    m = join_paths.load(label)
    import itertools
    names = sorted(set(m.graphs) | set(m.endpoints))
    pairs = set(itertools.combinations(names, 2))
    results = {}
    for a, b in sorted(pairs):
        r = m.find_join_paths(a, b)
        results[f"{a}|{b}"] = r
    agr = agreement(m)
    d = config.audit_dir()
    tool_counts = ((read_json(d / "a1b_tool_conformance.json", {}) or {}).get("tool_status_counts", {}) if d else {}) \
        or strategy.status_counts(m.catalog)
    h = m.cmp["headline"]
    data = {
        "run": m.run_dir.name, "graphs": names, "results": results, "showcase": SHOWCASE,
        "agreement": agr, "agree_counts": dict(collections.Counter(r["class"] for r in agr)),
        "headline": h, "tool_counts": tool_counts,
        "meter": (m.state or {}).get("meter_total"),
    }
    out = m.run_dir / "join_paths_demo.html"
    out.write_text(PAGE.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))), encoding="utf-8")
    return out


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Join Paths for MCP-OKN</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1b1d21;--quiet:#5d6470;--line:#e2e4e8;--accent:#1F6FB2;--soft:#e3eef8;--bad:#b42318;--badsoft:#fdecea;--good:#1a7f37;--goodsoft:#e7f5ec;--warn:#9a6700;--warnsoft:#fff6dd}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15171b;--panel:#1d2026;--ink:#e8eaee;--quiet:#9aa1ad;--line:#2e333b;--accent:#6aa8e0;--soft:#1d2c3b;--bad:#ff7b72;--badsoft:#3a1f22;--good:#56d364;--goodsoft:#1b3324;--warn:#e3b341;--warnsoft:#3a3020}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 24px 60px}
h1{font-size:26px;margin:0 0 6px}h2{font-size:19px;margin:38px 0 10px;padding-top:6px;border-top:1px solid var(--line)}h3{font-size:15px;margin:0 0 8px}
.lead{font-size:16.5px;color:var(--ink);max-width:880px;margin:0 0 6px}.sub{color:var(--quiet);font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:18px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.tile b{display:block;font-size:26px;font-variant-numeric:tabular-nums}.tile span{font-size:13px;color:var(--quiet)}
.tile.bad b{color:var(--bad)}.tile.good b{color:var(--good)}
.picker{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:8px 0 14px}
select{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:7px;background:var(--panel);color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}.chip{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:16px;padding:4px 11px;font-size:13px;cursor:pointer}.chip:hover,.chip.on{border-color:var(--accent);background:var(--soft)}
.cmp{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.card.today{border-left:4px solid var(--quiet)}.card.now{border-left:4px solid var(--accent)}
.label{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--quiet);margin-bottom:6px}
.status{display:inline-block;font-weight:600;padding:2px 10px;border-radius:12px;font-size:13.5px}
.s-known_non_join{background:var(--badsoft);color:var(--bad)}.s-unknown{background:var(--warnsoft);color:var(--warn)}.s-verified{background:var(--goodsoft);color:var(--good)}
.s-connect{background:var(--goodsoft);color:var(--good)}.s-other{background:var(--warnsoft);color:var(--warn)}
.note{font-size:13px;color:var(--quiet);margin-top:8px}.note q{color:var(--ink)}
table{border-collapse:collapse;width:100%;font-size:13.5px}td,th{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--quiet);font-weight:500}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.change{margin-top:12px;padding:8px 12px;border-radius:8px;background:var(--soft);font-size:14px}
details{margin-top:10px}summary{cursor:pointer;color:var(--accent);font-size:13.5px}pre{white-space:pre-wrap;word-break:break-all;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px;font-size:12px;max-height:220px;overflow:auto}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}.step{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}.step b{display:block;margin-bottom:4px}
.bar{display:flex;height:16px;border-radius:4px;overflow:hidden;margin:6px 0 4px;background:var(--line)}.bar i{display:block}
ul.tight{margin:6px 0;padding-left:20px}ul.tight li{margin:3px 0}
code{font-size:12.5px}
@media(max-width:820px){.cmp{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<h1>Join Paths for MCP-OKN</h1>
<p class="lead">MCP-OKN's <code>get_join_strategy</code> answers from a hand-curated catalog: one stored join per pair, with refusals that often rest on a note about one graph. <b><code>find_join_paths</code></b> answers from the identifiers each graph actually holds at its current release, and shows its evidence.</p>
<div class="sub" id="runline"></div>
<div class="tiles" id="tiles"></div>

<h2>Try any pair</h2>
<div class="chips" id="chips"></div>
<div class="picker"><select id="ga" aria-label="First graph"></select><span>×</span><select id="gb" aria-label="Second graph"></select></div>
<div class="cmp"><div class="card today" id="today"></div><div class="card now" id="now"></div></div>

<h2>Are the computed numbers right?</h2>
<p class="lead" id="agreeLead"></p>
<div class="bar" id="agreeBar"></div><div class="sub" id="agreeKey"></div>
<details><summary>All compared crosswalks</summary><table id="agreeTable"></table></details>

<h2>How it plugs into MCP-OKN</h2>
<div class="steps">
<div class="step"><b>1. A companion MCP tool (built)</b>A small MCP server, standard library only, exposing <code>find_join_paths</code>, <code>connections_of</code> and <code>list_graphs</code>. It can run beside MCP-OKN today, or the tool can move into MCP-OKN and replace refusals in <code>get_join_strategy</code>.</div>
<div class="step"><b>2. Refreshed per release</b>The map is recomputed when a graph's release changes; only changed graphs are re-read. With KGF's downloadable hashed key sets, each graph becomes one download and the 31 crosswalks that are too large today become testable.</div>
<div class="step"><b>3. Catalog fixes as pull requests</b>Each new or wrongly refused connection is drafted as a catalog entry in MCP-OKN's own format, for a maintainer to accept or reject.</div>
<div class="step"><b>4. Measured effect on an agent (research)</b>Same questions, an LLM agent with and without <code>find_join_paths</code>: how many cross-graph questions it answers, how many it wrongly refuses, and at what cost in tool calls and tokens.</div>
</div>
<details><summary>What a client sends and receives</summary><pre id="mcpEx"></pre></details>

<h2>Limits, stated plainly</h2>
<ul class="tight">
<li>Joins are on shared identifiers. Shared names (county names, industry sectors) are kept apart as weaker evidence.</li>
<li>A shared identifier says two graphs describe the same entity; whether a given question needs that join is the agent's or planner's decision.</li>
<li>Where an identifier set was too large to read (S2 cells, PubChem), the tool says "not measured" and never "cannot join".</li>
<li>"Today" is the real <code>get_join_strategy</code> answer recorded for all 903 pairs in the October audit, with the catalog dated 2026-09-26.</li>
</ul>
</div>
<script>
const D=/*DATA*/null;const $=s=>document.querySelector(s),fmt=n=>(n??0).toLocaleString(),esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const h=D.headline,tc=D.tool_counts||{},ac=D.agree_counts,agN=D.agreement.length;
$("#runline").textContent=`Computed map: run ${D.run} · ${D.graphs.length} graphs · read-only against the public FRINK federation${D.meter?` (${fmt(D.meter.requests)} requests, ${Math.round(D.meter.bytes/1e6)} MB)`:""}`;
const tiles=[["bad",h.contradicting_refusals_identifier_based,"pairs the tool refuses (“do not retry”) that share identifiers"],
["bad",h.new_identifier_based,"connected pairs the tool has no answer for (“unknown”)"],
["",h.pairs_where_connector_adds_entities,"pairs where Ubergraph or Wikidata adds entities a direct join misses"],
["good",`${(ac.exact||0)+(ac["within 5%"]||0)} / ${agN}`,"stored crosswalk counts the map reproduces within 5% (" + (ac.exact||0) + " exactly)"]];
$("#tiles").innerHTML=tiles.map(([c,n,s])=>`<div class="tile ${c}"><b>${typeof n==="number"?fmt(n):n}</b><span>${s}</span></div>`).join("");
// picker
const opt=D.graphs.map(g=>`<option>${g}</option>`).join("");$("#ga").innerHTML=opt;$("#gb").innerHTML=opt;
$("#chips").innerHTML=D.showcase.map(([a,b])=>`<button class="chip" data-a="${a}" data-b="${b}">${a} × ${b}</button>`).join("");
document.querySelectorAll(".chip").forEach(c=>c.onclick=()=>show(c.dataset.a,c.dataset.b));
$("#ga").onchange=$("#gb").onchange=()=>show($("#ga").value,$("#gb").value);
const STATUS={known_non_join:"Refuses: “do not retry”",unknown:"No answer (“unknown”)",verified:"Has a stored crosswalk","not recorded":"Not recorded"};
function get(a,b){return D.results[[a,b].sort().join("|")];}
function show(a,b){
  $("#ga").value=a;$("#gb").value=b;document.querySelectorAll(".chip").forEach(c=>c.classList.toggle("on",c.dataset.a===a&&c.dataset.b===b));
  if(a===b){$("#today").innerHTML="";$("#now").innerHTML="<p class=note>Pick two different graphs.</p>";return;}
  const r=get(a,b);
  if(!r){$("#today").innerHTML=`<div class=label>MCP-OKN get_join_strategy, today</div><p class=note>See the tool's answer in the audit for this pair.</p>`;
    $("#now").innerHTML=`<div class=label>find_join_paths, computed</div><span class="status s-other">No shared identifiers found</span><p class=note>No shared identifier in any scheme the catalog uses, at these releases, or one of the graphs was not fully read.</p>`;return;}
  const t=r.today_get_join_strategy;
  let L=`<div class=label>MCP-OKN get_join_strategy, today</div><span class="status s-${t.status}">${esc(STATUS[t.status]||t.status)}</span>`;
  if(t.stored_crosswalks.length)L+=`<p class=note>Stored crosswalk${t.stored_crosswalks.length>1?"s":""}: ${t.stored_crosswalks.map(s=>`${esc(s.id)} (${esc(s.shared_key)}, ${fmt(s.verified_count)})`).join("; ")}</p>`;
  (t.stored_elsewhere||[]).forEach(s=>L+=`<p class=note>The catalog stores ${fmt(s.count)} for this pair inside entry ${esc(s.in_entry)}, but the tool does not return it.</p>`);
  if(t.refusal_notes.length){const n=t.refusal_notes[0];L+=`<p class=note>${t.pair_specific?"Based on a check of this pair.":"Not based on a check of this pair: it rests on a note about <b>"+esc(n.about.replace(" only",""))+"</b>"}${n.attempted_key?`, about <q>${esc(n.attempted_key)}</q>`:""}.</p>`;}
  $("#today").innerHTML=L;
  const ok=r.verdict==="connect";
  let R=`<div class=label>find_join_paths, computed</div><span class="status ${ok?"s-connect":"s-other"}">${ok?"Connect":esc(r.verdict)}</span>`;
  if(r.direct_routes){R+=`<table style="margin-top:10px"><tr><th>Route</th><th class=n>Identifiers</th></tr>`+
    r.direct_routes.map(d=>`<tr><td>same ${esc(d.meaning)}</td><td class=n>${fmt(d.shared_identifiers)}</td></tr>`).join("")+
    (r.bridged_routes||[]).map(d=>`<tr><td>mapped through <b>${esc(d.through)}</b></td><td class=n>+${fmt(d.extra_identifiers)}</td></tr>`).join("")+`</table>`;}
  const ev=(r.evidence||[]).filter(s=>s[a].name||s[b].name).slice(0,3);
  if(ev.length)R+=`<p class=note><b>Same entity in both graphs</b> (sampled):</p><table>`+ev.map(s=>`<tr><td><code>${esc(s.identifier)}</code></td><td>${esc(s[a].name||"–")}</td><td>${esc(s[b].name||"–")}</td></tr>`).join("")+`</table>`;
  else if((r.evidence||[]).length)R+=`<p class=note>Sampled shared identifiers: ${r.evidence.slice(0,4).map(s=>`<code>${esc(s.identifier)}</code>`).join(", ")}</p>`;
  const src={};(r.evidence_queries||[]).forEach(q=>{(src[q.graph]=src[q.graph]||new Set());(q.pattern_from_crosswalks||[]).slice(0,1).forEach(x=>src[q.graph].add(x));});
  if(Object.keys(src).length)R+=`<p class=note><b>How the join is built:</b> each half reuses a query pattern from a crosswalk already verified in the MCP-OKN catalog: `+Object.entries(src).map(([g,xs])=>`${esc(g)} from <code>${[...xs].map(esc).join(", ")}</code>`).join("; ")+`.</p>`;
  if((r.two_hop_routes||[]).length)R+=`<p class=note><b>Also reachable in two hops:</b> ${r.two_hop_routes.map(x=>`via ${esc(x.via_graph)}`).join(", ")}</p>`;
  const rel=r.releases;R+=`<p class=note>Measured on ${esc(a)} ${esc(rel[a].kgf||"")} and ${esc(b)} ${esc(rel[b].kgf||"")} (run ${esc(r.measured_on_run)}).</p>`;
  if(r.note)R+=`<p class=note>${esc(r.note)}</p>`;
  if(r.change_vs_today&&r.change_vs_today!=="none")R+=`<div class=change>${esc(r.change_vs_today[0].toUpperCase()+r.change_vs_today.slice(1))}.</div>`;
  if((r.evidence_queries||[]).length)R+=`<details><summary>Queries that return these identifiers live</summary>`+r.evidence_queries.map(q=>`<p class=note>${esc(q.graph)}</p><pre>${esc(q.sparql)}</pre>`).join("")+`</details>`;
  $("#now").innerHTML=R;
}
show(...D.showcase[0]);
// agreement
const ex=ac.exact||0,cl=ac["within 5%"]||0,df=ac.differs||0;
$("#agreeLead").innerHTML=`For the ${agN} stored crosswalks the map reproduces directly, the computed count matches the count the catalog's own verified query returns <b>exactly in ${ex}</b> and <b>within 5% in ${cl} more</b>. That is the same answer from an independent method, for ${Math.round(100*(ex+cl)/agN)}% of them.`;
$("#agreeBar").innerHTML=`<i style="width:${100*ex/agN}%;background:var(--good)"></i><i style="width:${100*cl/agN}%;background:var(--accent)"></i><i style="width:${100*df/agN}%;background:var(--warn)"></i>`;
$("#agreeKey").innerHTML=`<span style="color:var(--good)">■</span> exact ${ex} &nbsp; <span style="color:var(--accent)">■</span> within 5% ${cl} &nbsp; <span style="color:var(--warn)">■</span> differs ${df} (listed below for checking; some of these join on titles or names rather than identifiers)`;
$("#agreeTable").innerHTML=`<tr><th>Crosswalk</th><th>Graphs</th><th>Key</th><th class=n>Catalog</th><th class=n>Computed</th><th>Match</th></tr>`+D.agreement.sort((x,y)=>x.class.localeCompare(y.class)).map(r=>`<tr><td>${esc(r.id)}</td><td>${esc(r.pair)}</td><td>${esc(r.key)}</td><td class=n>${fmt(r.catalog)}</td><td class=n>${fmt(r.computed)}</td><td>${esc(r.class)}</td></tr>`).join("");
// MCP example
const ex1=get("nde","rdkg");
$("#mcpEx").textContent=`→ {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"find_join_paths","arguments":{"graph_a":"nde","graph_b":"rdkg"}}}\n\n← result.content[0].text =\n`+JSON.stringify({pair:ex1.pair,today_get_join_strategy:{status:ex1.today_get_join_strategy.status},verdict:ex1.verdict,direct_routes:ex1.direct_routes,bridged_routes:ex1.bridged_routes,evidence:(ex1.evidence||[]).slice(0,1),change_vs_today:ex1.change_vs_today},null,2);
</script></body></html>"""

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ocm demo-page", description=__doc__)
    ap.add_argument("--label", help="run to use (default: the latest)")
    print(build(ap.parse_args(argv).label))


if __name__ == "__main__":
    main()
