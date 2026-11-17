"""Offline step: compute the connection map from the downloaded key sets.

  direct   graph A and graph B hold the same canonical identifier (same scheme)
  bridged  A holds x, a connector graph C maps x -> y, and B holds y (e.g. DOID -> MONDO)

Per graph pair it also measures entity-level reach: how many of A's identifiers reach B
directly, only through a connector, or either way (the audit's 20 / 147 / 151 question,
asked for every pair at once).
"""
from __future__ import annotations

import collections
import itertools
import time

from .common import read_json, read_keys


def load(run_dir, endpoints, bridges, state):
    graph_keys = collections.defaultdict(set)          # graph -> canonical keys
    sources = collections.defaultdict(list)            # (graph, scheme) -> endpoint ids
    for ep in endpoints:
        p = run_dir / "keys" / f"{ep['id']}.txt.gz"
        if state["endpoints"].get(ep["id"], {}).get("status") in ("ok", "ok_truncated", "ok_uncounted") and p.exists():
            ks = read_keys(p)
            graph_keys[ep["graph"]] |= ks
            for s in {k.split(":", 1)[0] for k in ks}:
                sources[(ep["graph"], s)].append(ep["id"])
    maps = collections.defaultdict(lambda: collections.defaultdict(set))   # connector -> x -> {y}
    for br in bridges:
        p = run_dir / "bridges" / f"{br['id']}.json"
        if state["bridges"].get(br["id"], {}).get("status") == "ok" and p.exists():
            for a, b in read_json(p, []):
                if a.split(":")[0] != b.split(":")[0]:          # only cross-scheme translations
                    maps[br["graph"]][a].add(b)
                    maps[br["graph"]][b].add(a)
    return graph_keys, maps, sources


def compute(graph_keys, maps):
    t0 = time.time()
    holders = collections.defaultdict(set)                   # key -> graphs holding it
    for g, ks in graph_keys.items():
        for k in ks:
            holders[k].add(g)
    # direct overlaps per (A, B, scheme)
    direct = collections.Counter()
    for k, gs in holders.items():
        if len(gs) > 1:
            scheme = k.split(":", 1)[0]
            for a, b in itertools.combinations(sorted(gs), 2):
                direct[(a, b, scheme)] += 1
    # entity-level reach per ordered pair (A -> B): which of A's keys reach B, and how
    reach_direct = collections.defaultdict(set)
    reach_bridge = collections.defaultdict(lambda: collections.defaultdict(set))   # (A,B) -> connector -> keys
    for a, ks in graph_keys.items():
        for k in ks:
            for b in holders[k]:
                if b != a:
                    reach_direct[(a, b)].add(k)
            for c, m in maps.items():
                if c == a or k not in m:
                    continue
                for y in m[k]:
                    for b in holders.get(y, ()):
                        if b not in (a, c):
                            reach_bridge[(a, b)][c].add(k)
    pairs = set(reach_direct) | set(reach_bridge)
    reach = []
    for (a, b) in sorted(pairs):
        d = reach_direct.get((a, b), set())
        via = reach_bridge.get((a, b), {})
        bridged_all = set().union(*via.values()) if via else set()
        either = d | bridged_all
        reach.append({
            "from": a, "to": b, "direct": len(d), "bridged": len(bridged_all), "either": len(either),
            "only_via_connector": len(either - d),
            "connectors": {c: len(ks) for c, ks in sorted(via.items(), key=lambda x: -len(x[1]))},
            "direct_schemes": dict(collections.Counter(k.split(":")[0] for k in d)),
            "bridged_schemes": dict(collections.Counter(k.split(":")[0] for k in bridged_all - d)),
        })
    direct_rows = [{"a": a, "b": b, "scheme": s, "shared": n} for (a, b, s), n in
                   sorted(direct.items(), key=lambda x: -x[1])]
    return {"direct": direct_rows, "reach": reach,
            "graphs": {g: {"keys": len(ks), "schemes": dict(collections.Counter(k.split(":")[0] for k in ks))}
                       for g, ks in sorted(graph_keys.items())},
            "connectors": {c: len(m) for c, m in maps.items()},
            "compute_seconds": round(time.time() - t0, 2)}
