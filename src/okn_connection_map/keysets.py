"""Live step: turn every catalog endpoint into a canonical key set (and every connector
pattern into a key-to-key mapping), using the public federation read-only.

For each endpoint: COUNT DISTINCT its join values; if not larger than the cap, download
them once (CSV), canonicalize in Python and store them gzipped. This is the client-side
stand-in for KGF's hashed key sets: when those are downloadable, only this step changes.
"""
from __future__ import annotations

import collections
import time

from .common import METER, log, read_json, read_keys, sparql_count, sparql_rows, utc_now, write_json, write_keys
from .schemes import canon_any, key_namespaces, label_key


def _q(ep, body):
    """Prepend the crosswalk's PREFIX declarations so the fragment stays valid SPARQL."""
    pre = ep.get("prefixes") or ""
    return f"{pre}\n{body}" if pre else body


def _where(ep):
    """The endpoint's WHERE body. A membership-only pattern (?k0 is a subject or object of
    any triple) is narrowed to the namespaces its keys can have; otherwise it would count
    every term in the graph."""
    frag = ep["fragment"]
    if ep.get("membership_only"):
        ns = key_namespaces(ep.get("hints", []), ep.get("namespaces", []))
        if ns:
            cond = " || ".join(f'STRSTARTS(STR(?k0), "{n}")' for n in ns)
            frag = f"{frag} FILTER({cond})"
    return frag


def _is_syntax_error(r):
    return "Invalid SPARQL" in (r.get("error") or "")


def canonicalize(values, hints):
    """Canonical keys for an endpoint's raw values.

    Identifier keys first. If almost nothing is a recognisable identifier and the values
    are plain strings (county names, industry sectors, species names), fall back to
    normalised label keys, which are reported as a separate, weaker kind of join."""
    keys, schemes, unmatched = set(), collections.Counter(), []
    for v in values:
        k = canon_any(v, hints)
        if k:
            keys.add(k)
            schemes[k.split(":", 1)[0]] += 1
        elif len(unmatched) < 5:
            unmatched.append(v)
    label_mode = False
    if values and len(keys) < 0.05 * len(values):
        labels = {lk for v in values if (lk := label_key(v))}
        if len(labels) >= 0.5 * len(values):
            keys |= labels
            schemes["LABEL"] += len(labels)
            label_mode = True
    return keys, schemes, unmatched, label_mode


def endpoint_keys(ep, cap, timeout, run_dir=None):
    where = _where(ep)
    n, r = sparql_count(_q(ep, f"SELECT (COUNT(DISTINCT ?k0) AS ?n) WHERE {{ {where} }}"), timeout)
    rec = {"distinct_values": n, "count_ms": r.get("elapsed_ms"), "narrowed": where != ep["fragment"]}
    if n is None and _is_syntax_error(r):
        rec.update(status="count_failed", error_kind=r.get("error_kind"), error=(r.get("error") or "")[:300])
        return rec, None
    if n == 0:
        rec["status"] = "empty"
        return rec, set()
    if n is not None and n > cap:
        rec["status"] = "too_large"
        return rec, None
    # When the count itself fails (e.g. the endpoint refuses the memory it needs), try
    # the download directly: a LIMITed DISTINCT is often cheaper than an exact count.
    d = sparql_rows(_q(ep, f"SELECT DISTINCT ?k0 WHERE {{ {where} }} LIMIT {cap + 1}"), timeout)
    rec.update(download_ms=d.get("elapsed_ms"), download_bytes=d.get("bytes"))
    if not d["ok"]:
        status = "count_failed" if n is None else "download_failed"
        rec.update(status=status, error_kind=d.get("error_kind") or r.get("error_kind"),
                   error=((d.get("error") or "") or (r.get("error") or ""))[:300])
        return rec, None
    values = [row.get("k0", "") for row in d["rows"]]
    if run_dir is not None:
        write_keys(run_dir / "raw" / f"{ep['id']}.txt.gz", {v.replace("\n", " ") for v in values})
    keys, schemes, unmatched, label_mode = canonicalize(values, ep["hints"])
    if n is None:
        status = "ok_uncounted" if len(values) <= cap else "ok_truncated"
    else:
        status = "ok" if len(values) >= 0.98 * n else "ok_truncated"
    rec.update(status=status, downloaded=len(values), canonical_keys=len(keys),
               schemes=dict(schemes), unmatched_examples=unmatched, label_mode=label_mode,
               value_examples=values[:3])
    return rec, keys


def bridge_pairs(br, cap, timeout):
    frag = br["fragment"]
    n, r = sparql_count(_q(br, f"SELECT (COUNT(*) AS ?n) WHERE {{ SELECT DISTINCT ?k0 ?k1 WHERE {{ {frag} }} }}"), timeout)
    rec = {"distinct_pairs": n}
    if n is None:
        rec.update(status="count_failed", error_kind=r.get("error_kind"), error=(r.get("error") or "")[:300])
        return rec, None
    if n == 0:
        rec["status"] = "empty"
        return rec, []
    if n > cap:
        rec["status"] = "too_large"
        return rec, None
    d = sparql_rows(_q(br, f"SELECT DISTINCT ?k0 ?k1 WHERE {{ {frag} }} LIMIT {cap + 1}"), timeout)
    if not d["ok"]:
        rec.update(status="download_failed", error_kind=d.get("error_kind"), error=(d.get("error") or "")[:300])
        return rec, None
    pairs, kinds = set(), collections.Counter()
    for row in d["rows"]:
        a, b = canon_any(row.get("k0", ""), br["hints"]), canon_any(row.get("k1", ""), br["hints"])
        if a and b and a != b:
            pairs.add((a, b))
            kinds[(a.split(":")[0], b.split(":")[0])] += 1
    rec.update(status="ok", downloaded=len(d["rows"]), canonical_pairs=len(pairs),
               scheme_pairs={f"{x}->{y}": c for (x, y), c in kinds.items()})
    return rec, sorted(pairs)


def run(run_dir, endpoints, bridges, cap=1_000_000, timeout=120.0, sleep=0.5, resume=True):
    state_path = run_dir / "keysets_state.json"
    state = read_json(state_path, {"endpoints": {}, "bridges": {}}) if resume else {"endpoints": {}, "bridges": {}}
    t0 = time.time()
    for i, ep in enumerate(endpoints, 1):
        if ep["id"] in state["endpoints"] and state["endpoints"][ep["id"]].get("status") in ("ok", "ok_truncated", "ok_uncounted", "empty", "too_large"):
            continue
        rec, keys = endpoint_keys(ep, cap, timeout, run_dir)
        rec["at"] = utc_now()
        if keys is not None:
            write_keys(run_dir / "keys" / f"{ep['id']}.txt.gz", keys)
        state["endpoints"][ep["id"]] = rec
        write_json(state_path, state)
        log(f"[{i:>3}/{len(endpoints)}] {ep['graph']:<28} {rec['status']:<15} "
            f"values={rec.get('distinct_values')} keys={rec.get('canonical_keys', '-')} {rec.get('schemes', '')}")
        time.sleep(sleep)
    for i, br in enumerate(bridges, 1):
        if br["id"] in state["bridges"] and state["bridges"][br["id"]].get("status") in ("ok", "empty", "too_large"):
            continue
        rec, pairs = bridge_pairs(br, cap, timeout)
        rec["at"] = utc_now()
        if pairs is not None:
            write_json(run_dir / "bridges" / f"{br['id']}.json", pairs)
        state["bridges"][br["id"]] = rec
        write_json(state_path, state)
        log(f"[bridge {i:>2}/{len(bridges)}] {br['graph']:<14} {rec['status']:<15} pairs={rec.get('canonical_pairs', rec.get('distinct_pairs'))} {rec.get('scheme_pairs', '')}")
        time.sleep(sleep)
    state["meter"] = METER.as_dict()
    state["wall_seconds"] = round(time.time() - t0, 1)
    write_json(state_path, state)
    return state


def recanonicalize(run_dir, endpoints, state):
    """Rebuild every key set from the saved raw values, without touching the network.
    Lets a later fix to the identifier patterns be applied to an existing run."""
    n = 0
    for ep in endpoints:
        rec = state["endpoints"].get(ep["id"])
        raw = run_dir / "raw" / f"{ep['id']}.txt.gz"
        if not rec or not raw.exists():
            continue
        keys, schemes, unmatched, label_mode = canonicalize(sorted(read_keys(raw)), ep["hints"])
        write_keys(run_dir / "keys" / f"{ep['id']}.txt.gz", keys)
        rec.update(canonical_keys=len(keys), schemes=dict(schemes), unmatched_examples=unmatched,
                   label_mode=label_mode)
        n += 1
    write_json(run_dir / "keysets_state.json", state)
    return n
