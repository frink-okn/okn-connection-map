"""Draft catalog entries for connections the catalog lacks, in MCP-OKN's own format.

For a direct connection the draft carries a runnable COUNT query made from the two
endpoints' patterns. When the two graphs spell the identifier differently (http vs https,
different hosts), the draft says so instead of guessing a rewrite: that rewrite is what a
maintainer should confirm.
"""
from __future__ import annotations

import re

from .common import utc_now

_VAR = re.compile(r"\?([A-Za-z_][A-Za-z0-9_]*)")


def _suffix(frag, tag):
    return _VAR.sub(lambda m: "?key" if m.group(1) == "k0" else f"?{m.group(1)}_{tag}", frag)


def _form(example, scheme):
    from .schemes import canonical
    k = canonical(example, scheme, numeric_ok=True)
    if not k:
        return None
    local = k.split(":", 1)[1]
    return example.replace(local, "{id}", 1) if local in example else None


def run(comparison, endpoints, state, sources, limit=25):
    eps = {e["id"]: e for e in endpoints}
    drafts = []
    for c in comparison["connections"]:
        if c["label"] == "confirmed" or not c["direct"]:
            continue
        scheme, shared = max(c["direct"].items(), key=lambda x: x[1])
        ea = (sources.get((c["a"], scheme)) or [None])[0]
        eb = (sources.get((c["b"], scheme)) or [None])[0]
        if not ea or not eb:
            continue
        fa = _form((state["endpoints"][ea].get("value_examples") or [""])[0], scheme)
        fb = _form((state["endpoints"][eb].get("value_examples") or [""])[0], scheme)
        same = fa is not None and fa == fb
        query = None
        if same:
            query = ("SELECT (COUNT(DISTINCT ?key) AS ?n) WHERE {\n  " + _suffix(eps[ea]["fragment"], "a") +
                     "\n  " + _suffix(eps[eb]["fragment"], "b") + "\n}")
        drafts.append({
            "id": f"AUTO-{scheme}-{c['a']}-{c['b']}",
            "left_kg": c["a"], "right_kg": c["b"], "shared_key": scheme, "bridge_kg": None,
            "verified_count": shared, "verified_on": utc_now()[:10],
            "provenance": "computed by okn-connection-map from catalog endpoint patterns",
            "label": c["label"], "tool_status_before": c["tool_status"],
            "identifier_forms": {c["a"]: fa, c["b"]: fb},
            "needs_normalization": not same,
            "skeleton_query": query,
        })
        if len(drafts) >= limit:
            break
    return drafts
