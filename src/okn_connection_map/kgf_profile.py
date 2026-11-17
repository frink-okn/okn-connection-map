"""Live, cheap step: what each graph is and holds, from services the PI's team already runs.

  * KGF catalogue: the release each dataset currently serves.
  * KGF /summary (JSON): the namespace inventory KGF computes at build time
    (distinct IRIs per curated prefix, by subject/object role).
  * okn-void: the version and last-load time the federation reports.
One request per graph plus two; nothing heavy.
"""
from __future__ import annotations

import urllib.parse

from .common import fetch_versions, get_json, log, utc_now
from . import config


def run(graphs):
    index, st = get_json(config.kgf_root())
    datasets = {d["id"]: d for d in (index or {}).get("datasets", [])} if st["ok"] else {}
    versions = fetch_versions()
    out = {"at": utc_now(), "kgf_ok": st["ok"], "graphs": {}}
    for g in sorted(graphs):
        d = datasets.get(g)
        rec = {"kgf_version": d.get("current") if d else None, "triples": d.get("triples") if d else None,
               "federation": versions.get(g), "namespaces": None}
        if d and "summary" in d.get("links", {}):
            url = urllib.parse.urljoin(config.kgf_root() + "/", d["links"]["summary"].lstrip("/").removeprefix("kgf/"))
            summ, s2 = get_json(url + "?format=json")
            ns = (summ or {}).get("namespaces") if s2["ok"] else None
            if ns:
                rows = sorted(ns.get("namespaces", []), key=lambda r: -(r.get("subject", 0) + r.get("object", 0)))
                rec["namespaces"] = [{k: r.get(k) for k in ("prefix", "namespace", "distinct_iris", "subject", "object")}
                                     for r in rows if (r.get("subject", 0) + r.get("object", 0)) > 0][:25]
                rec["iri_roles"] = ns.get("roles")
            else:
                rec["namespace_error"] = s2.get("error") or "summary has no namespace inventory"
        out["graphs"][g] = rec
        log(f"  {g:<30} kgf {rec['kgf_version']}  federation {(rec['federation'] or {}).get('version')}  "
            f"namespaces {len(rec['namespaces'] or [])}")
    return out
