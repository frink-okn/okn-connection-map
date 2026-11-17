"""What changed between two runs: connections gained, lost, or changed, beside the
release each graph served in each run."""
from __future__ import annotations

from .common import read_json, write_json


def _index(run_dir):
    cmp = read_json(run_dir / "comparison.json", {"connections": []})
    return {(c["a"], c["b"]): c for c in cmp["connections"]}, read_json(run_dir / "profile.json", {"graphs": {}})


def run(old_dir, new_dir):
    old, op = _index(old_dir)
    new, np_ = _index(new_dir)
    gained = [{"a": a, "b": b, "direct": new[(a, b)]["direct"], "via": new[(a, b)]["via"]} for a, b in new.keys() - old.keys()]
    lost = [{"a": a, "b": b, "direct": old[(a, b)]["direct"], "via": old[(a, b)]["via"]} for a, b in old.keys() - new.keys()]
    changed = []
    for k in new.keys() & old.keys():
        if new[k]["direct"] != old[k]["direct"] or new[k]["via"] != old[k]["via"]:
            changed.append({"a": k[0], "b": k[1], "before": {"direct": old[k]["direct"], "via": old[k]["via"]},
                            "after": {"direct": new[k]["direct"], "via": new[k]["via"]}})
    releases = {}
    for g in set(op["graphs"]) | set(np_["graphs"]):
        o, n = op["graphs"].get(g, {}), np_["graphs"].get(g, {})
        ov = (o.get("kgf_version"), (o.get("federation") or {}).get("last_updated"))
        nv = (n.get("kgf_version"), (n.get("federation") or {}).get("last_updated"))
        if ov != nv:
            releases[g] = {"before": ov, "after": nv}
    out = {"summary": {"gained": len(gained), "lost": len(lost), "changed": len(changed),
                       "graphs_with_new_release": len(releases)},
           "gained": gained, "lost": lost, "changed": changed, "releases": releases}
    write_json(new_dir / f"diff_vs_{old_dir.name}.json", out)
    return out
