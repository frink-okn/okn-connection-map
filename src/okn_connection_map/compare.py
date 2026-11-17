"""Offline step: set the computed map beside MCP-OKN's hand-curated catalog and the audit.

Every computed connection is labelled:
  confirmed            the catalog already has a crosswalk for this pair
  new                  no crosswalk, and the join tool answers "unknown"
  contradicts_refusal  no crosswalk, and the join tool answers "known non-join - do not retry"
Every catalog crosswalk is labelled reproduced / not reproduced (with the reason).
"""
from __future__ import annotations

import csv
import json

from . import config, strategy

CONNECTORS = {"ubergraph", "babel", "wikidata", "identifier-mappings", "okn-void"}


def _tool_status():
    """Answers recorded by an earlier audit of the live tool, if one is configured (OCM_AUDIT_DIR)."""
    d = config.audit_dir()
    p = d / "a1_pair_status.csv" if d else None
    if not p or not p.exists():
        return {}
    return {frozenset((r["kg_a"], r["kg_b"])): r["status"] for r in csv.DictReader(p.read_text(encoding="utf-8").splitlines())}


def _latest_b1():
    d = config.audit_dir()
    runs = sorted(d.glob("b1_freshness_*.json"), key=lambda p: p.stat().st_mtime) if d else []
    if not runs:
        return {}, None
    d = json.loads(runs[-1].read_text(encoding="utf-8"))
    return {r["id"]: r for r in d["rows"]}, d["summary"].get("label")


def run(catalog, parsed, endpoints, state, mp):
    tool = _tool_status()
    b1, b1_label = _latest_b1()
    ep_by_id = {e["id"]: e for e in endpoints}
    cat_pairs = {}
    for e in catalog["verified_crosswalks"]:
        for a, b in ((e.get("left_kg"), e.get("right_kg")),):
            if a and b:
                cat_pairs.setdefault(frozenset((a, b)), []).append(e["id"])

    # ---- connections (unordered pairs, connector graphs excluded from the endpoints)
    conns = {}
    for r in mp["direct"]:
        if r["a"] in CONNECTORS or r["b"] in CONNECTORS:
            continue
        c = conns.setdefault(frozenset((r["a"], r["b"])), {"a": r["a"], "b": r["b"], "direct": {}, "via": {}, "reach": {}})
        c["direct"][r["scheme"]] = r["shared"]
    for r in mp["reach"]:
        if r["from"] in CONNECTORS or r["to"] in CONNECTORS:
            continue
        key = frozenset((r["from"], r["to"]))
        c = conns.setdefault(key, {"a": min(r["from"], r["to"]), "b": max(r["from"], r["to"]), "direct": {}, "via": {}, "reach": {}})
        c["reach"][r["from"]] = {k: r[k] for k in ("direct", "bridged", "either", "only_via_connector")}
        for conn, n in r["connectors"].items():
            c["via"][conn] = max(c["via"].get(conn, 0), n)
    rows = []
    for key, c in conns.items():
        in_cat = key in cat_pairs
        # the recorded answer if an audit is configured, otherwise MCP-OKN's rules on this catalog
        status = tool.get(key) or strategy.join_strategy(catalog, c["a"], c["b"])["status"]
        if in_cat:
            label = "confirmed"
        elif status == "known_non_join":
            label = "contradicts_refusal"
        else:
            label = "new"
        best_reach = max(c["reach"].values(), key=lambda x: x["either"], default=None)
        rows.append({**c, "label": label, "tool_status": status, "catalog_ids": cat_pairs.get(key, []),
                     "direct_total": sum(c["direct"].values()),
                     "kind": "direct" if c["direct"] else "via connector only",
                     # a connection seen only through shared names (no shared identifier)
                     "label_only": not c["via"] and set(c["direct"]) <= {"LABEL"},
                     "best_reach": best_reach})
    rows.sort(key=lambda r: (-r["direct_total"], -max(r["via"].values(), default=0)))

    # ---- catalog reproduction
    by_parsed = {p["id"]: p for p in parsed["crosswalks"]}
    skipped = {s["id"]: s["reason"] for s in parsed["skipped"]}
    repro = []
    for e in catalog["verified_crosswalks"]:
        a, b = e.get("left_kg"), e.get("right_kg")
        p = by_parsed.get(e["id"])
        r = {"id": e["id"], "a": a, "b": b, "shared_key": e.get("shared_key"), "bridge_kg": e.get("bridge_kg"),
             "stored": e.get("verified_count"),
             "live_oct": b1.get(e["id"], {}).get("live_count"), "live_class": b1.get(e["id"], {}).get("class")}
        if not p:
            r.update(status="not_parsed", reason=skipped.get(e["id"], "unknown"))
        else:
            sts = [state["endpoints"].get(p[s], {}).get("status") for s in ("left", "right")]
            c = conns.get(frozenset((a, b))) if a not in CONNECTORS and b not in CONNECTORS else None
            if any(s in ("too_large",) for s in sts):
                r.update(status="awaiting_keysets", reason="an endpoint is larger than the download cap")
            elif any(s not in ("ok", "ok_truncated", "ok_uncounted", "empty") for s in sts):
                r.update(status="endpoint_failed", reason=",".join(str(s) for s in sts))
            elif a in CONNECTORS or b in CONNECTORS:
                r.update(status="connector_pair", reason="one side is a connector graph")
            elif c and (sum(c["direct"].values()) or c["via"]):
                r.update(status="reproduced", computed_direct=c["direct"], computed_via=c["via"])
            else:
                r.update(status="not_found_now", reason="no shared identifiers in today's data")
        repro.append(r)

    graphs_in_map = {g for c in rows for g in (c["a"], c["b"])}
    lab = lambda x: sum(1 for r in rows if r["label"] == x)
    head = {
        "graphs_profiled": len(mp["graphs"]),
        "graphs_connected": len(graphs_in_map),
        "connections_total": len(rows),
        "connections_confirmed": lab("confirmed"),
        "connections_new": lab("new"),
        "connections_contradicting_refusals": lab("contradicts_refusal"),
        "catalog_crosswalks": len(repro),
        "catalog_reproduced": sum(1 for r in repro if r["status"] == "reproduced"),
        "catalog_testable": sum(1 for r in repro if r["status"] in ("reproduced", "not_found_now")),
        "catalog_not_found_now": sum(1 for r in repro if r["status"] == "not_found_now"),
        "catalog_awaiting_keysets": sum(1 for r in repro if r["status"] == "awaiting_keysets"),
        "connections_identifier_based": sum(1 for r in rows if not r["label_only"]),
        "connections_label_only": sum(1 for r in rows if r["label_only"]),
        "new_identifier_based": sum(1 for r in rows if r["label"] == "new" and not r["label_only"]),
        "contradicting_refusals_identifier_based": sum(1 for r in rows if r["label"] == "contradicts_refusal" and not r["label_only"]),
        "pairs_where_connector_adds_entities": sum(1 for r in rows if r["best_reach"] and r["best_reach"]["only_via_connector"] > 0),
        "b1_label": b1_label,
    }
    return {"headline": head, "connections": rows, "catalog": repro}
