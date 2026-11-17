"""find_join_paths: how two FRINK graphs connect, from a computed connection map.

A proposed companion to MCP-OKN's get_join_strategy. For a pair of graphs it returns,
side by side:

  today     what get_join_strategy answers now (verified / unknown / known_non_join, and
            the catalog note a refusal rests on), computed with MCP-OKN's own rules from
            the current catalog (see strategy.py);
  computed  every route the data support: shared identifiers per scheme, reach added by a
            mapping graph (Ubergraph, Wikidata), and two-hop routes through a third graph,
            each with counts and the release it was measured on;
  evidence  sample shared identifiers with their names in both graphs, and small
            per-graph queries that return those identifiers live;
  verdict   connect / no shared identifiers found / not measured.

It never answers "does not join" for a pair whose identifier sets were not fully read.

Usage (see `ocm paths --help`):
  ocm paths nde rdkg                 # one pair, readable
  ocm paths nde rdkg --json          # one pair, as the MCP tool returns it
  ocm paths nde rdkg --live          # also re-check the evidence against FRINK now
  ocm paths nde                      # everything one graph reaches
  ocm paths --label 2026-10-15c ...  # pick the run (default: latest)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from functools import lru_cache
from pathlib import Path

from . import config, strategy
from .common import load_catalog, read_json

OK = ("ok", "ok_truncated", "ok_uncounted", "empty")
SCHEME_WORDS = {
    "MONDO": "MONDO disease", "DOID": "Disease Ontology disease", "HP": "HPO phenotype",
    "NCIT": "NCIt concept", "Entrez": "NCBI Gene", "Ensembl": "Ensembl gene", "UniProt": "UniProt protein",
    "CAS": "CAS chemical", "CHEBI": "ChEBI chemical", "DrugBank": "DrugBank drug", "NCBITaxon": "NCBI taxon",
    "ZIP5": "ZIP code", "county_FIPS": "county (FIPS)", "state_FIPS": "state (FIPS)", "dbSNP": "dbSNP variant",
    "UMLS": "UMLS concept", "MeSH": "MeSH term", "UBERON": "UBERON anatomy", "CL": "cell type", "EFO": "EFO term",
    "LABEL": "shared name (weaker evidence)",
}


def latest_run() -> Path:
    # the most recently computed run (folder names like "trial" do not sort by date)
    root = config.runs_dir()
    runs = sorted((p for p in root.iterdir() if (p / "comparison.json").exists()),
                  key=lambda p: (p / "comparison.json").stat().st_mtime) if root.exists() else []
    if not runs:
        sys.exit(f"No computed run under {root}.\n"
                 "Either compute one (ocm all --label <name>) or copy the included sample: ocm use-sample")
    return runs[-1]


class ConnectionMap:
    """Read-only view of one okn-connection-map run plus the audit's record of the tool."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.cmp = read_json(run_dir / "comparison.json")
        self.map = read_json(run_dir / "map.json")
        self.plan = read_json(run_dir / "plan.json", {}) or {}
        self.state = read_json(run_dir / "keysets_state.json", {}) or {}
        self.profile = (read_json(run_dir / "profile.json", {}) or {}).get("graphs", {})
        self.catalog = load_catalog(required=False) or self._run_catalog()
        self.conns = {frozenset((c["a"], c["b"])): c for c in self.cmp["connections"]}
        self.reach = {(r["from"], r["to"]): r for r in self.map.get("reach", [])}
        self.graphs = sorted(self.map.get("graphs", {}))
        self.tool = self._tool_status()
        self.verify = self._verify_samples()
        self._raw_cache = {}
        self.endpoints = {}
        for ep in self.plan.get("endpoints", []):
            st = self.state.get("endpoints", {}).get(ep["id"], {}).get("status", "not_run")
            self.endpoints.setdefault(ep["graph"], []).append((ep, st))
        self.adj = {}
        for c in self.cmp["connections"]:
            if c.get("label_only"):
                continue
            w = max(sum(v for s, v in c["direct"].items() if s != "LABEL"), max(c["via"].values(), default=0))
            self.adj.setdefault(c["a"], []).append((c["b"], w, c))
            self.adj.setdefault(c["b"], []).append((c["a"], w, c))

    # ---- what the tool says today -------------------------------------------------
    def _run_catalog(self):
        """Fallback: the catalog snapshot saved with the run, if any."""
        return read_json(self.run_dir / "catalog_snapshot.json", {}) or {}

    def _tool_status(self):
        """Answers recorded by an earlier audit of the live tool (optional, OCM_AUDIT_DIR)."""
        out = {}
        d = config.audit_dir()
        p = d / "a1_pair_status.csv" if d else None
        if p and p.exists():
            for r in csv.DictReader(p.read_text(encoding="utf-8").splitlines()):
                out[frozenset((r["kg_a"], r["kg_b"]))] = r["status"]
        return out

    def today(self, a, b):
        """get_join_strategy's answer for the pair, with what it rests on."""
        js = strategy.join_strategy(self.catalog, a, b)
        status = self.tool.get(frozenset((a, b))) or js["status"]
        res = {"status": status, "computed_from": "recorded audit" if frozenset((a, b)) in self.tool
               else "MCP-OKN rules applied to the catalog", "catalog_verified_on": self.catalog.get("verified_on"),
               "stored_crosswalks": js.get("joins", []), "refusal_notes": js.get("non_joins", [])}
        if "pair_specific" in js:
            res["pair_specific"] = js["pair_specific"]
        # counts the catalog keeps for this pair inside another entry, which the tool does not return
        for e in self.catalog.get("verified_crosswalks", []):
            sec = e.get("verified_count_secondary")
            if isinstance(sec, dict) and e.get("left_kg") in (a, b):
                other = b if e["left_kg"] == a else a
                if other in sec:
                    res.setdefault("stored_elsewhere", []).append(
                        {"in_entry": e["id"], "shared_key": e.get("shared_key"), "count": sec[other]})
        return res

    # ---- what the data say ----------------------------------------------------------
    def _verify_samples(self):
        out = {}
        p = self.run_dir / "verify.csv"
        if p.exists():
            for r in csv.DictReader(p.read_text(encoding="utf-8").splitlines()):
                out.setdefault(frozenset((r["a"], r["b"])), []).append(r)
        return out

    def release(self, g):
        p = self.profile.get(g) or {}
        fed = p.get("federation") or {}
        return {"kgf": p.get("kgf_version"), "federation": fed.get("version") if isinstance(fed, dict) else None,
                "loaded": (fed.get("last_updated") or "")[:10] if isinstance(fed, dict) else None}

    def coverage(self, g):
        """Were this graph's identifier sets fully read? (decides whether 'no join' may be said)"""
        sts = [st for _, st in self.endpoints.get(g, [])]
        return {"patterns": len(sts), "read": sum(st in OK for st in sts),
                "not_read": sum(st not in OK for st in sts)}

    def _evidence(self, a, b, c):
        rows = self.verify.get(frozenset((a, b)), [])
        samples = []
        for r in rows[:6]:
            ra, rb = (r["raw_a"], r["raw_b"]) if r["a"] == a else (r["raw_b"], r["raw_a"])
            la, lb = (r["label_a"], r["label_b"]) if r["a"] == a else (r["label_b"], r["label_a"])
            samples.append({"identifier": r["key"], "scheme": r["scheme"],
                            a: {"as_written": ra, "name": la or None}, b: {"as_written": rb, "name": lb or None}})
        return samples

    def _evidence_queries(self, a, b, samples):
        """Per-graph queries that return the sampled identifiers live, using, for each scheme,
        the graph pattern that actually yielded identifiers of that scheme in the run."""
        out = []
        for g in (a, b):
            by_scheme = {}
            for smp in samples:
                if smp[g]["as_written"]:
                    by_scheme.setdefault(smp["scheme"], []).append(smp[g]["as_written"])
            for scheme, raws in by_scheme.items():
                ep = self._raw_holder(g, raws) or self._holder_pattern(g, scheme)
                if ep is None:
                    continue
                terms = " ".join(f"<{v}>" if v.startswith(("http://", "https://")) else json.dumps(v)
                                 for v in dict.fromkeys(raws))
                frag = _narrowed(ep)
                if "AS ?k0" in frag:
                    # the pattern creates ?k0 with BIND: the values must join after it
                    body = f"{{ {frag} }} VALUES ?k0 {{ {terms} }}"
                else:
                    # bind the values first, so the endpoint looks up only these identifiers
                    body = f"VALUES ?k0 {{ {terms} }} {frag}"
                q = f"{ep.get('prefixes') or ''}\nSELECT DISTINCT ?k0 WHERE {{ {body} }}".strip()
                out.append({"graph": g, "scheme": scheme, "expect": len(set(raws)),
                            "pattern_from_crosswalks": ep.get("crosswalks", [])[:4], "sparql": q})
        return out

    def _raw_holder(self, g, raws):
        """The pattern whose saved raw download contains these exact spellings (most precise)."""
        from .common import read_keys
        best, n = None, 0
        for ep, st in self.endpoints.get(g, []):
            p = self.run_dir / "raw" / f"{ep['id']}.txt.gz"
            if st not in OK or not p.exists():
                continue
            if ep["id"] not in self._raw_cache:
                self._raw_cache[ep["id"]] = read_keys(p)
            hit = sum(v in self._raw_cache[ep["id"]] for v in raws)
            if hit > n:
                best, n = ep, hit
        return best

    def _holder_pattern(self, g, scheme):
        best, n = None, 0
        for ep, st in self.endpoints.get(g, []):
            if st not in OK:
                continue
            c = (self.state.get("endpoints", {}).get(ep["id"], {}).get("schemes") or {}).get(scheme, 0)
            if c > n:
                best, n = ep, c
        return best

    def two_hop(self, a, b, k=3):
        routes = []
        for mid, w1, c1 in self.adj.get(a, []):
            if mid == b:
                continue
            for nxt, w2, c2 in self.adj.get(mid, []):
                if nxt == b:
                    routes.append({"via_graph": mid, "first_hop": _how(c1), "second_hop": _how(c2),
                                   "at_most": min(w1, w2)})
        return sorted(routes, key=lambda r: -r["at_most"])[:k]

    def find_join_paths(self, a, b):
        if a not in self.graphs and a not in self.endpoints:
            return {"error": f"unknown graph '{a}'", "graphs": self.graphs}
        if b not in self.graphs and b not in self.endpoints:
            return {"error": f"unknown graph '{b}'", "graphs": self.graphs}
        c = self.conns.get(frozenset((a, b)))
        today = self.today(a, b)
        cov = {a: self.coverage(a), b: self.coverage(b)}
        res = {"pair": [a, b], "today_get_join_strategy": today,
               "releases": {a: self.release(a), b: self.release(b)},
               "measured_on_run": self.run_dir.name, "coverage": cov}
        if c:
            direct = [{"scheme": s, "meaning": SCHEME_WORDS.get(s, s), "shared_identifiers": n}
                      for s, n in sorted(c["direct"].items(), key=lambda kv: -kv[1])]
            bridged = [{"through": k, "extra_identifiers": n} for k, n in sorted(c["via"].items(), key=lambda kv: -kv[1])]
            ra, rb = self.reach.get((a, b)), self.reach.get((b, a))
            samples = self._evidence(a, b, c)
            ident = [d for d in direct if d["scheme"] != "LABEL"]
            res.update({
                "verdict": "connect" if (ident or bridged) else "shared names only",
                "direct_routes": direct,
                "bridged_routes": bridged,
                "reach": {f"{a} -> {b}": _r(ra), f"{b} -> {a}": _r(rb)},
                "two_hop_routes": self.two_hop(a, b),
                "evidence": samples,
                "evidence_queries": self._evidence_queries(a, b, samples) if samples else [],
                "change_vs_today": _change(today["status"], ident or bridged),
            })
        else:
            unread = cov[a]["not_read"] + cov[b]["not_read"]
            res.update({
                "verdict": "not measured" if unread else "no shared identifiers found",
                "note": ("Some identifier sets of these graphs were too large or failed to download, so the "
                         "map does not claim the pair cannot join." if unread else
                         "No shared identifier in any scheme the catalog uses, at these releases."),
                "two_hop_routes": self.two_hop(a, b),
            })
        return res

    def connections_of(self, g):
        out = []
        for other, w, c in sorted(self.adj.get(g, []), key=lambda t: -t[1]):
            r = self.reach.get((g, other)) or {}
            out.append({"graph": other, "shared": {s: n for s, n in c["direct"].items() if s != "LABEL"},
                        "via": c["via"], "reach_from_" + g: r.get("either"),
                        "today": self.tool.get(frozenset((g, other)))
                                 or strategy.join_strategy(self.catalog, g, other)["status"]})
        return {"graph": g, "release": self.release(g), "connects_to": out, "measured_on_run": self.run_dir.name}


def _narrowed(ep):
    try:
        from .keysets import _where
        return _where(ep)
    except Exception:
        return ep["fragment"]


def _how(c):
    d = {s: n for s, n in c["direct"].items() if s != "LABEL"}
    return ("/".join(d) if d else "via " + "/".join(c["via"])) + f" ({max(list(d.values()) + list(c['via'].values()), default=0):,})"


def _r(r):
    if not r:
        return None
    return {"direct": r["direct"], "only_via_connector": r["only_via_connector"], "either": r["either"]}


def _change(status, connects):
    if not connects:
        return "none"
    return {"known_non_join": "tool refuses a pair the data connect",
            "unknown": "tool has no answer; the data connect",
            "verified": "tool already has a crosswalk; the map adds counts, routes and release"}.get(status, "")


@lru_cache(maxsize=4)
def load(label: str | None = None) -> ConnectionMap:
    return ConnectionMap(config.runs_dir() / label if label else latest_run())


def _print(res):
    if "error" in res:
        print(res["error"]); return
    a, b = res["pair"]
    t = res["today_get_join_strategy"]
    print(f"\n{a} x {b}   (map run {res['measured_on_run']})")
    print(f"  TODAY  get_join_strategy -> {t['status']}")
    for j in t.get("stored_crosswalks", [])[:3]:
        cnt = f"{j['verified_count']:,}" if isinstance(j.get("verified_count"), int) else (j.get("verified_count") or "?")
        print(f"         catalog crosswalk {j['id']}: {j.get('shared_key')} ({cnt})")
    for n in t.get("stored_elsewhere", []):
        print(f"         (catalog entry {n['in_entry']} stores {n['count']} for this pair, but the tool does not return it)")
    for n in t["refusal_notes"][:2]:
        print(f"         rests on a note about {n['about']}: {n['attempted_key']}")
    print(f"  MAP    verdict: {res['verdict']}")
    for d in res.get("direct_routes", []):
        print(f"         shared {d['meaning']:30} {d['shared_identifiers']:>8,}")
    for d in res.get("bridged_routes", []):
        print(f"         + through {d['through']:24} {d['extra_identifiers']:>8,} more")
    for s in res.get("evidence", [])[:3]:
        print(f"         e.g. {s['identifier']:22} {a}: {s[a]['name'] or '-'} | {b}: {s[b]['name'] or '-'}")
    for q in res.get("evidence_queries", []):
        src = ", ".join(q.get("pattern_from_crosswalks", [])[:2])
        print(f"  HOW    {q['graph']:22} {q['scheme']:12} pattern reused from catalog crosswalk {src}")
    for r in res.get("two_hop_routes", []):
        print(f"         2-hop via {r['via_graph']}: {r['first_hop']} then {r['second_hop']}")
    if res.get("note"):
        print("         " + res["note"])


def run_live(res):
    """Run the evidence queries against the live FRINK endpoint and report what came back."""
    from .common import sparql_rows
    out = []
    for q in res.get("evidence_queries", []):
        d = sparql_rows(q["sparql"], 180.0)
        got = len({r.get("k0") for r in d.get("rows", [])}) if d.get("ok") else None
        out.append({"graph": q["graph"], "scheme": q["scheme"], "expected": q["expect"], "returned": got,
                    "error": None if d.get("ok") else (d.get("error") or "")[:160]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ocm paths", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("graphs", nargs="+", help="one graph (everything it reaches) or two graphs (how they connect)")
    ap.add_argument("--label", help="run to use (default: the latest)")
    ap.add_argument("--json", action="store_true", help="print the full answer as JSON, as the MCP tool returns it")
    ap.add_argument("--live", action="store_true", help="also run the evidence queries against FRINK now")
    a = ap.parse_args(argv)
    m = load(a.label)
    res = m.find_join_paths(*a.graphs[:2]) if len(a.graphs) > 1 else m.connections_of(a.graphs[0])
    if a.live and len(a.graphs) > 1:
        res["live_check"] = run_live(res)
    if a.json or len(a.graphs) == 1:
        print(json.dumps(res, indent=2))
    else:
        _print(res)
        for c in res.get("live_check", []):
            got = "query failed: " + c["error"] if c["returned"] is None else f"{c['returned']} of {c['expected']} returned"
            print(f"  LIVE   {c['graph']:22} {c['scheme']:12} sampled identifiers: {got}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
