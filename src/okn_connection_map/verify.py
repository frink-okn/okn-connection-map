"""Live step: spot-check the connections the map claims, before anyone relies on them.

For every connection labelled "new" or "contradicts a refusal" (and a seeded sample of
"confirmed" ones as a control), it samples up to 5 shared identifiers per scheme and asks
the live endpoint, for each of the two graphs:
  1. is the identifier still there, in the same join pattern the map used?
  2. what is it called there (a label, name or title), so a reader can judge whether both
     graphs mean the same entity?

Writes runs/<label>/verify.csv (one row per sampled identifier) and verify_summary.json.
Connections seen only through a connector graph or only through shared names are listed
but not sampled: they need a different check.
"""
from __future__ import annotations

import csv
import random
import time

from .common import GRAPH_PREFIX, log, read_json, read_keys, sparql_rows, write_json
from .keysets import _q, _where
from .schemes import canon_any

XSD_INT = "http://www.w3.org/2001/XMLSchema#integer"
LABELISH = ('CONTAINS(LCASE(STR(?p)), "label") || CONTAINS(LCASE(STR(?p)), "name") || '
            'CONTAINS(LCASE(STR(?p)), "title") || CONTAINS(LCASE(STR(?p)), "prefterm")')


def _term(v):
    """A raw CSV value back as a SPARQL term (CSV results do not say IRI or literal)."""
    if v.startswith(("http://", "https://")):
        return [f"<{v}>"]
    lit = v.replace("\\", "\\\\").replace('"', '\\"')
    out = [f'"{lit}"']
    if v.isdigit():
        out.append(f'"{v}"^^<{XSD_INT}>')
    return out


class Sources:
    """Per-graph, per-scheme key sets and the raw spelling behind each canonical key."""

    def __init__(self, run_dir, endpoints, state):
        self.run_dir, self.state = run_dir, state
        self.by_graph = {}
        for ep in endpoints:
            if state["endpoints"].get(ep["id"], {}).get("status") in ("ok", "ok_truncated", "ok_uncounted"):
                self.by_graph.setdefault(ep["graph"], []).append(ep)
        self._keys, self._raw = {}, {}

    def keys(self, ep):
        if ep["id"] not in self._keys:
            p = self.run_dir / "keys" / f"{ep['id']}.txt.gz"
            self._keys[ep["id"]] = read_keys(p) if p.exists() else set()
        return self._keys[ep["id"]]

    def raw(self, ep):
        """canonical key -> one raw value, from the saved raw download (if this run has it)."""
        if ep["id"] not in self._raw:
            p = self.run_dir / "raw" / f"{ep['id']}.txt.gz"
            m = {}
            if p.exists():
                for v in sorted(read_keys(p)):
                    k = canon_any(v, ep["hints"])
                    if k and k not in m:
                        m[k] = v
            self._raw[ep["id"]] = m
        return self._raw[ep["id"]]

    def scheme_keys(self, graph, scheme):
        out = set()
        for ep in self.by_graph.get(graph, []):
            out |= {k for k in self.keys(ep) if k.split(":", 1)[0] == scheme}
        return out

    def holder(self, graph, key):
        """The endpoint of `graph` that holds `key`, and the raw spelling it has there."""
        for ep in self.by_graph.get(graph, []):
            if key in self.keys(ep):
                return ep, self.raw(ep).get(key)
        return None, None


def _present(ep, raws, timeout):
    """Which of the raw values the endpoint's join pattern still returns, live."""
    terms = " ".join(t for v in raws for t in _term(v))
    # The values join after the pattern: many patterns create ?k0 with BIND(... AS ?k0),
    # and SPARQL forbids binding a variable that a VALUES block before it already set.
    d = sparql_rows(_q(ep, f"SELECT DISTINCT ?k0 WHERE {{ {{ {_where(ep)} }} VALUES ?k0 {{ {terms} }} }}"), timeout)
    if not d["ok"]:
        return None, d.get("error", "")[:200]
    return {r.get("k0", "") for r in d["rows"]}, None


def _labels(graph, raws, timeout):
    iris = [v for v in raws if v.startswith(("http://", "https://"))]
    if not iris:
        return {}
    vals = " ".join(f"<{v}>" for v in iris)
    q = (f"SELECT ?k0 (SAMPLE(?l) AS ?label) WHERE {{ VALUES ?k0 {{ {vals} }} "
         f"GRAPH <{GRAPH_PREFIX}{graph}> {{ ?k0 ?p ?l . FILTER(isLiteral(?l) && STRLEN(STR(?l)) < 150 && ({LABELISH})) }} }} "
         f"GROUP BY ?k0")
    d = sparql_rows(q, timeout)
    return {r.get("k0", ""): r.get("label", "") for r in d["rows"]} if d["ok"] else {}


def run(run_dir, endpoints, state, per_scheme=5, controls=10, timeout=120.0, sleep=0.3, seed=42):
    cmp = read_json(run_dir / "comparison.json")
    src = Sources(run_dir, endpoints, state)
    rng = random.Random(seed)
    conns = [c for c in cmp["connections"] if c["label"] in ("new", "contradicts_refusal")]
    confirmed = [c for c in cmp["connections"] if c["label"] == "confirmed"]
    conns += rng.sample(confirmed, min(controls, len(confirmed)))

    rows, summary = [], []
    for i, c in enumerate(conns, 1):
        a, b = c["a"], c["b"]
        rec = {"a": a, "b": b, "label": c["label"], "direct": c["direct"], "via": c["via"],
               "sampled": 0, "present_both": 0, "present_a": 0, "present_b": 0, "errors": []}
        schemes = [s for s in sorted(c["direct"], key=lambda s: -c["direct"][s]) if s != "LABEL"][:2]
        if not schemes:
            rec["note"] = "via a connector graph only" if c["via"] else "shared names only (label join)"
            summary.append(rec)
            log(f"[{i:>2}/{len(conns)}] {a} x {b}: {rec['note']}, not sampled")
            continue
        for s in schemes:
            shared = sorted(src.scheme_keys(a, s) & src.scheme_keys(b, s))
            sample = rng.sample(shared, min(per_scheme, len(shared)))
            sides = {}
            for g in (a, b):
                picks = [(k, *src.holder(g, k)) for k in sample]
                eps = {}
                for k, ep, raw in picks:
                    if ep is not None and raw:
                        eps.setdefault(ep["id"], (ep, []))[1].append(raw)
                live = set()
                for ep, raws in eps.values():
                    got, err = _present(ep, raws, timeout)
                    if err:
                        rec["errors"].append(f"{g}: {err}")
                    live |= got or set()
                    time.sleep(sleep)
                labels = _labels(g, [r for _, _, r in picks if r], timeout)
                time.sleep(sleep)
                sides[g] = {k: (raw, (raw in live) if raw else None, labels.get(raw or "", "")) for k, _, raw in picks}
            for k in sample:
                ra, pa, la = sides[a][k]
                rb, pb, lb = sides[b][k]
                rows.append({"a": a, "b": b, "connection": c["label"], "scheme": s, "key": k,
                             "raw_a": ra or "", "present_a": pa, "label_a": la,
                             "raw_b": rb or "", "present_b": pb, "label_b": lb})
                rec["sampled"] += 1
                rec["present_a"] += bool(pa)
                rec["present_b"] += bool(pb)
                rec["present_both"] += bool(pa and pb)
        summary.append(rec)
        log(f"[{i:>2}/{len(conns)}] {a} x {b} ({c['label']}): {rec['present_both']}/{rec['sampled']} "
            f"sampled identifiers present in both graphs live")

    out = run_dir / "verify.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["a", "b", "connection", "scheme", "key", "raw_a", "present_a",
                                          "label_a", "raw_b", "present_b", "label_b"])
        w.writeheader()
        w.writerows(rows)
    sampled = [r for r in summary if r["sampled"]]
    total = {"connections_checked": len(summary), "connections_sampled": len(sampled),
             "identifiers_sampled": sum(r["sampled"] for r in sampled),
             "identifiers_present_both": sum(r["present_both"] for r in sampled),
             "connections_all_present": sum(1 for r in sampled if r["present_both"] == r["sampled"])}
    write_json(run_dir / "verify_summary.json", {"total": total, "connections": summary})
    return total
