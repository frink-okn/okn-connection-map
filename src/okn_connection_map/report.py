"""Offline step: one self-contained HTML report of a run (no network, no external files)."""
from __future__ import annotations

import html
import math

from .common import read_json

CONNECTORS = {"ubergraph", "babel", "wikidata", "identifier-mappings", "okn-void"}
LABEL_TEXT = {"confirmed": "In the catalog", "new": "Not in the catalog",
              "contradicts_refusal": "Catalog says “do not retry”"}
COLORS = {"confirmed": "#9C948E", "new": "#1F6FB2", "contradicts_refusal": "#C00000"}
e = lambda x: html.escape(str(x))
fmt = lambda n: f"{n:,}" if isinstance(n, int) else ("–" if n is None else e(n))


def _schemes(d):
    return ", ".join(f"{s} {fmt(n)}" for s, n in sorted(d.items(), key=lambda x: -x[1])) or "–"


def _network(conns, width=760, height=620, min_shared=5):
    graphs = sorted({g for c in conns for g in (c["a"], c["b"])})
    if not graphs:
        return "<p>No connections.</p>"
    cx, cy, r = width / 2, height / 2, min(width, height) / 2 - 95
    pos = {g: (cx + r * math.cos(2 * math.pi * i / len(graphs) - math.pi / 2),
               cy + r * math.sin(2 * math.pi * i / len(graphs) - math.pi / 2)) for i, g in enumerate(graphs)}
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Connection network">']
    order = {"confirmed": 0, "new": 1, "contradicts_refusal": 2}
    for c in sorted(conns, key=lambda c: order[c["label"]]):
        if max(c["direct_total"], max(c["via"].values(), default=0)) < min_shared:
            continue
        (x1, y1), (x2, y2) = pos[c["a"]], pos[c["b"]]
        n = max(c["direct_total"], max(c["via"].values(), default=0), 1)
        w = 0.6 + 1.1 * math.log10(n)
        dash = ' stroke-dasharray="4 3"' if not c["direct"] else ""
        op = 0.45 if c["label"] == "confirmed" else 0.85
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{COLORS[c["label"]]}" '
                   f'stroke-width="{w:.2f}" stroke-opacity="{op}"{dash}><title>{e(c["a"])} – {e(c["b"])}: '
                   f'{e(LABEL_TEXT[c["label"]])}; {e(_schemes(c["direct"]))}</title></line>')
    for g, (x, y) in pos.items():
        ang = math.atan2(y - cy, x - cx)
        tx, ty = x + 10 * math.cos(ang), y + 10 * math.sin(ang)
        anchor = "start" if math.cos(ang) > 0.15 else ("end" if math.cos(ang) < -0.15 else "middle")
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#1D1B1A"/>'
                   f'<text x="{tx:.1f}" y="{ty + 4:.1f}" text-anchor="{anchor}" class="nlabel">{e(g)}</text>')
    out.append("</svg>")
    return "".join(out)


def run(run_dir):
    cmp = read_json(run_dir / "comparison.json")
    mp = read_json(run_dir / "map.json")
    st = read_json(run_dir / "keysets_state.json")
    prof = read_json(run_dir / "profile.json", {"graphs": {}})
    plan = read_json(run_dir / "plan.json")
    drafts = read_json(run_dir / "catalog_additions_draft.json", [])
    h = cmp["headline"]
    meter = st.get("meter_total") or st.get("meter") or {}
    conns = cmp["connections"]
    eps = {x["id"]: x for x in plan["endpoints"]}
    ep_status = {}
    for k, v in st["endpoints"].items():
        ep_status[v.get("status")] = ep_status.get(v.get("status"), 0) + 1

    tiles = [
        (fmt(h["connections_total"]), f"graph pairs connected, across {h['graphs_connected']} graphs"),
        (f"{h['catalog_reproduced']} / {h['catalog_testable']}", "testable catalog crosswalks reproduced automatically"),
        (fmt(h.get("new_identifier_based", h["connections_new"]) + h.get("contradicting_refusals_identifier_based", h["connections_contradicting_refusals"])),
         "connections on shared identifiers that the catalog does not list"
         + (f" (plus {h['connections_label_only']} on shared names only, shown separately)" if h.get("connections_label_only") else "")),
        (fmt(h.get("contradicting_refusals_identifier_based", h["connections_contradicting_refusals"])),
         "of them where the join tool says “do not retry”"),
        (fmt(h["pairs_where_connector_adds_entities"]), "pairs where a connector graph reaches entities a direct match misses"),
        (f"{meter.get('requests', 0):,} req · {meter.get('bytes', 0) / 1e6:.0f} MB · {meter.get('seconds', 0) / 60:.1f} min",
         f"what one full run asked of FRINK; the map itself computes in {mp['compute_seconds']} s"),
    ]
    tile_html = "".join(f'<div class="tile{" hot" if i in (2, 3) else ""}"><div class="big">{a}</div><div>{b}</div></div>'
                        for i, (a, b) in enumerate(tiles))

    missing = [c for c in conns if c["label"] != "confirmed" and not c.get("label_only")]
    names_only = [c for c in conns if c["label"] != "confirmed" and c.get("label_only")]
    rows_names = "".join(
        f"<tr><td>{e(c['a'])} × {e(c['b'])}</td><td class='n'>{fmt(c['direct'].get('LABEL', 0))}</td>"
        f"<td class='{c['label']}'>{e(LABEL_TEXT[c['label']])}</td></tr>" for c in names_only)
    rows_missing = "".join(
        f"<tr><td>{e(c['a'])} × {e(c['b'])}</td><td>{e(_schemes(c['direct']))}</td>"
        f"<td>{e(', '.join(f'{k} {fmt(v)}' for k, v in c['via'].items()) or '–')}</td>"
        f"<td class='{c['label']}'>{e(LABEL_TEXT[c['label']])}</td></tr>" for c in missing[:60])

    reach = sorted([c for c in conns if c["best_reach"] and c["best_reach"]["only_via_connector"] > 0],
                   key=lambda c: -c["best_reach"]["only_via_connector"])
    rows_reach = ""
    for c in reach[:25]:
        frm = max(c["reach"].items(), key=lambda kv: kv[1]["only_via_connector"])
        src, r = frm
        dst = c["b"] if src == c["a"] else c["a"]
        rows_reach += (f"<tr><td>{e(src)} → {e(dst)}</td><td class='n'>{fmt(r['direct'])}</td>"
                       f"<td class='n hotc'>{fmt(r['only_via_connector'])}</td><td class='n'>{fmt(r['either'])}</td>"
                       f"<td>{e(', '.join(c['via']))}</td></tr>")

    cat = cmp["catalog"]
    by = {}
    for r in cat:
        by.setdefault(r["status"], []).append(r)
    cat_summary = "".join(f"<li><b>{len(v)}</b> {e(k.replace('_', ' '))}</li>" for k, v in sorted(by.items(), key=lambda x: -len(x[1])))
    rows_nf = "".join(f"<tr><td>{e(r['id'])}</td><td>{e(r['a'])} × {e(r['b'])}</td><td>{e(r['shared_key'])}</td>"
                      f"<td class='n'>{fmt(r['stored'])}</td><td class='n'>{fmt(r.get('live_oct'))}</td></tr>"
                      for r in by.get("not_found_now", []))
    too_large = [(eps[k]["graph"], v.get("distinct_values"), eps[k]["hints"]) for k, v in st["endpoints"].items()
                 if v.get("status") == "too_large" and k in eps]
    rows_big = "".join(f"<tr><td>{e(g)}</td><td>{e(', '.join(hh))}</td><td class='n'>{fmt(n)}</td></tr>" for g, n, hh in sorted(too_large, key=lambda x: -(x[1] or 0)))
    rows_prof = ""
    for g, p in sorted(prof.get("graphs", {}).items()):
        if g in CONNECTORS or g not in mp["graphs"]:
            continue
        fed = (p.get("federation") or {})
        mism = p.get("kgf_version") and fed.get("version") and p["kgf_version"] != fed.get("version")
        ns = ", ".join(f"{n['prefix']} {fmt(n['subject'] + n['object'])}" for n in (p.get("namespaces") or [])[:4])
        rows_prof += (f"<tr><td>{e(g)}</td><td>{e(p.get('kgf_version') or '–')}</td>"
                      f"<td class='{'contradicts_refusal' if mism else ''}'>{e(fed.get('version') or '–')}</td>"
                      f"<td>{e((fed.get('last_updated') or '')[:10] or '–')}</td>"
                      f"<td>{e(_schemes(mp['graphs'][g]['schemes']))}</td><td class='small'>{e(ns or '–')}</td></tr>")
    rows_drafts = "".join(f"<tr><td>{e(d['left_kg'])} × {e(d['right_kg'])}</td><td>{e(d['shared_key'])}</td>"
                          f"<td class='n'>{fmt(d['verified_count'])}</td>"
                          f"<td>{'needs a format rewrite' if d['needs_normalization'] else 'runnable query drafted'}</td></tr>"
                          for d in drafts[:15])

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OKN connection map</title>
<style>
:root {{ --red:#C00000; --ink:#1D1B1A; --muted:#625D59; --pale:#F5F1ED; --palered:#F9E7E5; --blue:#1F6FB2; }}
body {{ margin:0; background:#fff; color:var(--ink); font:15px/1.5 Georgia, "Times New Roman", serif; }}
header {{ background:var(--red); color:#fff; padding:14px 32px; font:600 13px/1 system-ui, sans-serif; letter-spacing:.04em; }}
main {{ max-width:1180px; margin:0 auto; padding:24px 32px 60px; }}
h1 {{ font-size:34px; margin:18px 0 4px; }} h2 {{ font-size:22px; margin:40px 0 6px; border-bottom:3px solid var(--red); padding-bottom:6px; }}
.sub {{ color:var(--muted); margin:0 0 18px; }}
.tiles {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
.tile {{ background:var(--pale); padding:14px 16px; }} .tile.hot {{ background:var(--palered); }}
.big {{ font-size:28px; font-weight:700; }} .tile.hot .big {{ color:var(--red); }}
.two {{ display:grid; grid-template-columns: 1.15fr .85fr; gap:24px; align-items:start; }}
svg {{ width:100%; height:auto; }} .nlabel {{ font:11px system-ui, sans-serif; fill:#1D1B1A; }}
.legend span {{ display:inline-block; margin-right:16px; font:13px system-ui, sans-serif; }}
.legend i {{ display:inline-block; width:22px; height:3px; vertical-align:middle; margin-right:6px; }}
table {{ border-collapse:collapse; width:100%; font:13px/1.4 system-ui, sans-serif; margin-top:8px; }}
th {{ text-align:left; color:var(--red); font-size:11px; text-transform:uppercase; letter-spacing:.04em; padding:6px; border-bottom:1px solid #D8D0CA; }}
td {{ padding:6px; border-bottom:1px solid #EEE8E3; vertical-align:top; }} td.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.contradicts_refusal, td.hotc {{ color:var(--red); font-weight:600; }} td.new {{ color:var(--blue); font-weight:600; }}
td.small {{ color:var(--muted); font-size:12px; }} .note {{ color:var(--muted); font-size:13px; }}
ul.flat {{ list-style:none; padding:0; display:flex; flex-wrap:wrap; gap:8px 22px; font:14px system-ui, sans-serif; }}
@media (max-width:820px) {{ .tiles {{ grid-template-columns:1fr; }} .two {{ grid-template-columns:1fr; }} main {{ padding:16px; }} }}
</style></head><body>
<header>FRINK / OKN CONNECTION MAP</header><main>
<h1>How the OKN graphs connect: computed, not curated</h1>
<p class="sub">Run <b>{e(run_dir.name)}</b>. Built from the endpoint patterns in MCP-OKN's crosswalk catalog
(catalog dated {e(plan.get('catalog_verified_on'))}), key sets read once from the public FRINK federation,
releases from KGF and okn-void. Read-only throughout.</p>
<div class="tiles">{tile_html}</div>

<h2>The map</h2>
<div class="two"><div>{_network(conns)}</div><div>
<p class="legend"><span><i style="background:{COLORS['confirmed']}"></i>in the catalog</span>
<span><i style="background:{COLORS['new']}"></i>not in the catalog</span>
<span><i style="background:{COLORS['contradicts_refusal']}"></i>catalog says “do not retry”</span></p>
<p class="note">Each line is a pair of graphs that share identifiers today. Dashed: connected only through a connector
graph (for example DOID → MONDO in Ubergraph). Width grows with the number of shared identifiers; pairs sharing fewer than 5 are not drawn. Connector graphs
themselves (Ubergraph, Babel, Wikidata) are left out of the drawing.</p>
<p class="note">Identifiers are compared after reduction to one canonical form per scheme (e.g. <code>MONDO:0005015</code>,
<code>ZIP5:19104</code>), so different spellings of the same identifier in different graphs still match.</p>
</div></div>

<h2>Connections the catalog does not list</h2>
<p class="note">Highest overlap first. Every row is a candidate crosswalk an agent could use today.</p>
<table><tr><th>Graphs</th><th>Shared identifiers (direct)</th><th>Through a connector</th><th>Catalog / join tool</th></tr>{rows_missing}</table>
{('<h3>On shared names only</h3><p class="note">These pairs share normalised names (county names, industry sectors, species names) but no identifier. A shared name is weaker evidence: many states have a Washington County. Check before adding to the catalog.</p><table><tr><th>Graphs</th><th>Shared names</th><th>Catalog / join tool</th></tr>' + rows_names + '</table>') if rows_names else ''}

<h2>Where a connector graph reaches what a direct match misses</h2>
<p class="note">Entity-level reach: of the source graph's identifiers, how many reach the other graph directly, how many only
through a connector, and how many either way. The audit's tuberculosis case (20 / 147 / 151) is one of these rows.</p>
<table><tr><th>From → to</th><th>Direct</th><th>Only via connector</th><th>Either</th><th>Connectors</th></tr>{rows_reach}</table>

<h2>The catalog, re-derived</h2>
<ul class="flat">{cat_summary}</ul>
<p class="note">"Reproduced": the computed map finds the same pair connected. "Not found now": the pair shares no identifiers
in today's data. "Awaiting key sets": an endpoint was larger than the download cap; KGF's hashed key sets remove this limit.
"Not parsed": the crosswalk's query uses a shape the first version does not split (unions, VALUES, multi-graph blocks).</p>
<table><tr><th>Crosswalk</th><th>Graphs</th><th>Key</th><th>Stored</th><th>Live (audit)</th></tr>{rows_nf}</table>

<h2>Draft catalog additions</h2>
<p class="note">In MCP-OKN's format, in <code>catalog_additions_draft.json</code>. Where the two graphs spell the identifier the same way,
a runnable COUNT query is drafted; where they differ, the draft names both forms for a maintainer to confirm.</p>
<table><tr><th>Graphs</th><th>Key</th><th>Count</th><th>Status</th></tr>{rows_drafts}</table>

<h2>Endpoints awaiting KGF key sets</h2>
<p class="note">Too large to download as values within the cap. With KGF's downloadable hashed key sets these become one request each.</p>
<table><tr><th>Graph</th><th>Catalog key</th><th>Distinct values</th></tr>{rows_big or '<tr><td colspan=3>None</td></tr>'}</table>

<h2>Graph profiles</h2>
<p class="note">Release served by KGF and by the federation (red when they differ), identifiers found by this run, and the
largest namespaces in KGF's own namespace inventory.</p>
<table><tr><th>Graph</th><th>KGF</th><th>Federation</th><th>Loaded</th><th>Identifiers found</th><th>KGF namespaces</th></tr>{rows_prof}</table>

<h2>Method and limits</h2>
<p class="note">1. The 193 catalog crosswalks are split into per-graph endpoint patterns ({len(plan['endpoints'])} in scope) and
connector patterns ({len(plan['bridges'])}). 2. Each endpoint's distinct join values are counted and, under the cap, read once and reduced
to canonical identifiers ({e(', '.join(f'{k} {v}' for k, v in ep_status.items()))}). 3. Every pair of graphs is intersected per scheme,
and connector mappings are composed for bridged reach. 4. Results are set beside the catalog, the join tool's answers and the October
audit. Limits: only identifier schemes the catalog already uses are profiled; biomedical and geographic schemes only; connector
patterns are those the catalog contains. Counts say identifiers are shared, not that every question across the pair is meaningful.</p>
</main></body></html>"""
    out = run_dir / "report.html"
    out.write_text(doc, encoding="utf-8")
    return out
