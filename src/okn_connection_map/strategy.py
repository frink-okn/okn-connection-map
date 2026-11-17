"""What MCP-OKN's `get_join_strategy(kg_a, kg_b)` answers for a pair, computed offline.

This mirrors the rules in MCP-OKN (src/mcp_okn/tools/joins.py and crosswalks.py,
checked against the 2026-09-26 source), applied to the same catalog file:

  1. "verified"        if any catalog crosswalk touches both graphs
                       (as left_kg, right_kg, bridge_kg or a listed member);
  2. "known_non_join"  otherwise, if a known-non-join record names both graphs,
                       or names either graph on its own (a note about a single graph);
  3. "unknown"         otherwise.

Rule 2's second half is why many refusals rest on a note about one graph rather than
on a check of the pair. If MCP-OKN changes these rules, update this file to match.
"""
from __future__ import annotations

import itertools
from collections import Counter


def entry_kgs(entry: dict) -> set:
    kgs = {entry[k] for k in ("left_kg", "right_kg", "bridge_kg") if entry.get(k)}
    kgs.update(entry.get("members", []) or [])
    return kgs


def nonjoin_kgs(entry: dict) -> set:
    return {entry[k] for k in ("left_kg", "right_kg", "kg") if entry.get(k)}


def join_strategy(catalog: dict, a: str, b: str) -> dict:
    joins = [e for e in catalog.get("verified_crosswalks", []) if {a, b} <= entry_kgs(e)]
    if joins:
        return {"status": "verified", "verified_on": catalog.get("verified_on"),
                "joins": [{"id": e.get("id"), "shared_key": e.get("shared_key"),
                           "verified_count": e.get("verified_count"), "bridge": e.get("bridge_kg"),
                           "verified_on": e.get("verified_on")} for e in joins]}
    nonj = []
    for e in catalog.get("known_non_joins", []):
        kgs = nonjoin_kgs(e)
        if {a, b} <= kgs:
            nonj.append({"about": "this pair", "attempted_key": e.get("attempted_key"),
                         "diagnosis": (e.get("diagnosis") or "")[:400]})
        elif e.get("kg") in (a, b):
            nonj.append({"about": f"{e['kg']} only", "attempted_key": e.get("attempted_key"),
                         "diagnosis": (e.get("diagnosis") or "")[:400]})
    if nonj:
        return {"status": "known_non_join", "verified_on": catalog.get("verified_on"), "non_joins": nonj,
                "pair_specific": any(n["about"] == "this pair" for n in nonj)}
    return {"status": "unknown", "verified_on": catalog.get("verified_on")}


def catalog_graphs(catalog: dict) -> list:
    gs = set()
    for e in catalog.get("verified_crosswalks", []):
        gs |= entry_kgs(e)
    for e in catalog.get("known_non_joins", []):
        gs |= nonjoin_kgs(e)
    return sorted(gs)


def status_counts(catalog: dict, graphs=None) -> dict:
    """How often each answer comes back over every pair of graphs."""
    graphs = sorted(graphs or catalog_graphs(catalog))
    c = Counter(join_strategy(catalog, a, b)["status"] for a, b in itertools.combinations(graphs, 2))
    return {"pairs": sum(c.values()), **dict(c)}
