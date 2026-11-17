"""ocm: compute where the Proto-OKN / FRINK knowledge graphs connect.

Start here (each command explains itself with --help):

  ocm check                         test that this computer can reach the OKN services
  ocm fetch-catalog                 download MCP-OKN's crosswalk catalog (needed once)
  ocm strategy nde rdkg             what MCP-OKN's get_join_strategy answers for a pair today
  ocm use-sample                    copy the included sample run (October 2026), to try things offline
  ocm sparql --file examples/queries/*.rq     run the example queries against FRINK
  ocm kgf                           list the graph releases FRINK's KGF service serves

  ocm paths nde rdkg                how two graphs connect, with evidence (uses a computed run)
  ocm followup --label L            which of a run's findings the catalog has added since

  ocm all --label L                 compute a full run (about 100 minutes; resumable)
  ocm all --label L --only nde,rdkg,ubergraph     a quick trial on a few graphs
  ocm demo-page --label L           write runs/L/join_paths_demo.html
  ocm mcp                           serve find_join_paths to an AI agent (MCP, stdio)

Global option: --home PATH  folder for downloads and results (default ./ocm-data, or $OCM_HOME).
Read-only toward every service.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
from datetime import date

from . import __version__, config, strategy
from .common import METER, USER_AGENT, get_json, load_catalog, log, read_json, sparql_rows, utc_now, write_json

PIPELINE = ["all", "plan", "profile", "keysets", "map", "report", "explore", "verify", "recanon", "diff"]


# ---------------------------------------------------------------- setup and checks
def cmd_fetch_catalog(a):
    url = a.url or config.catalog_url()
    dest = config.catalog_path()
    log(f"Downloading the MCP-OKN crosswalk catalog\n  from {url}\n  to   {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e}\nIf your network blocks GitHub, download the file in a browser and point to it:\n"
            f"  set OCM_CATALOG=C:\\path\\to\\crosswalks.json   (Windows)\n"
            f"  export OCM_CATALOG=/path/to/crosswalks.json  (macOS/Linux)")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        old = dest.with_name(f"crosswalks.{(read_json(dest, {}) or {}).get('verified_on', 'previous')}.json")
        shutil.copyfile(dest, old)
        log(f"  kept the previous copy as {old.name}")
    dest.write_bytes(raw)
    log(f"OK: {len(data.get('verified_crosswalks', []))} crosswalks, {len(data.get('known_non_joins', []))} "
        f"known non-joins, catalog verified_on {data.get('verified_on')}")
    return 0


def cmd_check(a):
    """Five quick tests, each explained, so a failure says what to fix."""
    ok_all = True

    def line(ok, what, detail):
        nonlocal ok_all
        ok_all &= bool(ok) or ok is None
        mark = {True: "PASS", False: "FAIL", None: "SKIP"}[ok]
        print(f"  [{mark}] {what:<34} {detail}")

    print(f"okn-connection-map {__version__}   (Python {sys.version.split()[0]})")
    line(sys.version_info >= (3, 9), "Python 3.9 or newer", sys.executable)
    h = config.home()
    try:
        h.mkdir(parents=True, exist_ok=True)
        import os
        line(os.access(h, os.W_OK), "working folder is writable", str(h))
    except OSError as e:
        line(False, "working folder is writable", f"{h}: {e}")
    cat = load_catalog(required=False)
    if cat:
        line(True, "crosswalk catalog present", f"{len(cat.get('verified_crosswalks', []))} crosswalks, "
                                                f"verified_on {cat.get('verified_on')}  ({config.catalog_path()})")
    else:
        line(None, "crosswalk catalog present", "not yet - run: ocm fetch-catalog")
    if a.offline:
        line(None, "FRINK SPARQL endpoint", "skipped (--offline)")
        line(None, "FRINK KGF service", "skipped (--offline)")
    else:
        q = ("SELECT (COUNT(DISTINCT ?s) AS ?graphs) WHERE { GRAPH <https://purl.org/okn/frink/kg/okn-void> "
             "{ ?s <http://purl.org/pav/version> ?v } }")
        r = sparql_rows(q, timeout=60)
        if r["ok"] and r["rows"]:
            line(True, "FRINK SPARQL endpoint", f"{config.sparql_endpoint()}  ({next(iter(r['rows'][0].values()))} "
                                                f"graphs report a version, {r['elapsed_ms']:.0f} ms)")
        else:
            line(False, "FRINK SPARQL endpoint", f"{config.sparql_endpoint()}: {r.get('error_kind')} {str(r.get('error'))[:120]}")
        idx, st = get_json(config.kgf_root(), timeout=60)
        if st["ok"]:
            line(True, "FRINK KGF service", f"{config.kgf_root()}  ({len((idx or {}).get('datasets', []))} datasets)")
        else:
            line(False, "FRINK KGF service", f"{config.kgf_root()}: {st.get('error')}")
    runs = sorted(p.name for p in config.runs_dir().glob("*") if (p / "comparison.json").exists()) \
        if config.runs_dir().exists() else []
    line(None if not runs else True, "computed runs available", ", ".join(runs) or
         "none yet - compute one (ocm all ...) or copy the included sample: ocm use-sample")
    print("\nAll required checks passed." if ok_all else "\nSome checks failed: see docs/10_troubleshooting.md")
    return 0 if ok_all else 1


def cmd_strategy(a):
    cat = load_catalog()
    if a.all:
        print(json.dumps(strategy.status_counts(cat), indent=2))
        return 0
    if not a.graph_b:
        gs = strategy.catalog_graphs(cat)
        rows = [(b, strategy.join_strategy(cat, a.graph_a, b)["status"]) for b in gs if b != a.graph_a]
        for b, s in sorted(rows, key=lambda t: (t[1], t[0])):
            print(f"  {a.graph_a} x {b:<34} {s}")
        return 0
    res = strategy.join_strategy(cat, a.graph_a, a.graph_b)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"get_join_strategy({a.graph_a}, {a.graph_b}) -> {res['status']}   (catalog verified_on {res.get('verified_on')})")
    for j in res.get("joins", []):
        print(f"  crosswalk {j['id']}: {j.get('shared_key')}  count {j.get('verified_count')}"
              + (f"  through {j['bridge']}" if j.get("bridge") else ""))
    for n in res.get("non_joins", []):
        print(f"  refusal note about {n['about']}: {n['attempted_key']}")
    return 0


def _sample_dir():
    from pathlib import Path
    here = Path(__file__).resolve()
    for base in (here.parents[2], Path.cwd()):        # a cloned repository, or the current folder
        d = base / "sample_results"
        if d.is_dir():
            return d
    return None


def cmd_use_sample(a):
    """Copy the included October run into the working folder, so every offline command works at once."""
    src = _sample_dir()
    if not src:
        log("Cannot find the sample_results folder. Run this command from inside the cloned repository."); return 1
    for run in sorted(p for p in src.iterdir() if (p / "comparison.json").exists()):
        dest = config.runs_dir() / run.name
        shutil.copytree(run, dest, dirs_exist_ok=True)
        log(f"copied sample run {run.name} -> {dest}")
    log("Try:  ocm paths nde rdkg      then open the report.html in that folder")
    return 0


def cmd_sparql(a):
    """Run one read-only SELECT against the FRINK federation and print or save the rows."""
    from pathlib import Path
    import glob
    # Windows' Command Prompt does not expand *.rq, so expand patterns here
    files = [Path(f) for pat in (a.file or []) for f in (sorted(glob.glob(pat)) if any(c in pat for c in "*?[") else [pat])]
    queries = [(f.name, f.read_text(encoding="utf-8")) for f in files] or [("query", a.query or "")]
    if not queries[0][1].strip():
        log("Give a query in quotes, or --file path/to/query.rq"); return 1
    rc = 0
    for name, q in queries:
        expect = next((ln.split(":", 1)[1].strip() for ln in q.splitlines() if ln.lower().startswith("# expected")), None)
        r = sparql_rows(q, timeout=a.timeout)
        if not r["ok"]:
            log(f"{name}: FAILED ({r.get('error_kind')}) {str(r.get('error'))[:300]}"); rc = 1; continue
        log(f"{name}: {len(r['rows'])} rows in {r['elapsed_ms']:.0f} ms" + (f"   (expected: {expect})" if expect else ""))
        if a.out and len(queries) == 1:
            import csv
            with open(a.out, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=r["columns"]); w.writeheader(); w.writerows(r["rows"])
            log(f"  saved to {a.out}")
        else:
            for row in r["rows"][: a.limit]:
                log("  " + " | ".join(f"{k}={v}" for k, v in row.items()))
            if len(r["rows"]) > a.limit:
                log(f"  ... {len(r['rows']) - a.limit} more (use --out file.csv to save all)")
    return rc


def cmd_kgf(a):
    """What KGF serves: every dataset with its current release, or one dataset's full entry."""
    idx, st = get_json(config.kgf_root(), timeout=60)
    if not st["ok"]:
        log(f"Cannot reach {config.kgf_root()}: {st.get('error')}"); return 1
    ds = (idx or {}).get("datasets", [])
    if a.dataset:
        d = next((d for d in ds if d.get("id") == a.dataset), None)
        if not d:
            log(f"No dataset '{a.dataset}'. Known: {', '.join(sorted(x.get('id', '') for x in ds))}"); return 1
        print(json.dumps(d, indent=2))
        return 0
    for d in sorted(ds, key=lambda d: d.get("id", "")):
        t = d.get("triples")
        print(f"  {d.get('id', ''):<36} release {str(d.get('current')):<12} "
              f"{(f'{t:,}' if isinstance(t, int) else '?'):>15} triples   links: {', '.join(sorted(d.get('links', {})))}")
    print(f"\n{len(ds)} datasets. Details of one (including its links): ocm kgf <dataset>")
    return 0


# ---------------------------------------------------------------- follow-up on a run
def cmd_followup(a):
    """Which connections the run found outside the catalog have since been added to it."""
    from .join_paths import latest_run
    run_dir = config.runs_dir() / a.label if a.label else latest_run()
    cmp = read_json(run_dir / "comparison.json")
    if not cmp:
        log(f"No comparison.json in {run_dir}"); return 1
    cat = load_catalog()
    rows = []
    for c in cmp["connections"]:
        if c["label"] == "confirmed" or c.get("label_only"):
            continue
        js = strategy.join_strategy(cat, c["a"], c["b"])
        direct = {s: n for s, n in c["direct"].items() if s != "LABEL"}
        now = [{"id": j["id"], "shared_key": j.get("shared_key"), "count": j.get("verified_count"),
                "verified_on": j.get("verified_on")} for j in js.get("joins", [])]
        agree = None
        for j in now:
            if isinstance(j["count"], int) and j["count"] in direct.values():
                agree = "same count"
        rows.append({"pair": [c["a"], c["b"]], "at_run": c["label"], "computed": direct, "via": c["via"],
                     "now": js["status"], "catalog_entries_now": now, "agreement": agree})
    added = [r for r in rows if r["now"] == "verified"]
    out = {"run": run_dir.name, "catalog_verified_on": cat.get("verified_on"), "checked_at": utc_now(),
           "summary": {"found_outside_catalog_at_run": len(rows), "added_since": len(added),
                       "added_with_same_count": sum(r["agreement"] == "same count" for r in added),
                       "still_missing": len(rows) - len(added),
                       "still_refused": sum(r["now"] == "known_non_join" for r in rows)},
           "rows": sorted(rows, key=lambda r: (r["now"] != "verified", -sum(r["computed"].values())))}
    write_json(run_dir / "catalog_followup.json", out)
    s = out["summary"]
    print(f"Run {run_dir.name} against the catalog verified_on {cat.get('verified_on')}:")
    print(f"  {s['found_outside_catalog_at_run']} identifier connections were outside the catalog when the run was made")
    print(f"  {s['added_since']} have been added since ({s['added_with_same_count']} with exactly the count the map computed)")
    print(f"  {s['still_missing']} are still missing; {s['still_refused']} of them are refused (\"do not retry\")\n")
    for r in out["rows"][: a.top]:
        tot = sum(r["computed"].values())
        found = f"{tot:>7,}" if tot else "  via " + "/".join(r["via"])
        ids = ", ".join(f"{e['id']} ({e['count']})" for e in r["catalog_entries_now"][:2])
        pair = f"{r['pair'][0]} x {r['pair'][1]}"
        print(f"  {'ADDED' if r['now'] == 'verified' else 'open '}  {pair:<40} map {found:>10}   "
              f"now: {r['now']}{'  ' + ids if ids else ''}")
    print(f"\nFull list: {run_dir / 'catalog_followup.json'}")
    return 0


# ---------------------------------------------------------------- the pipeline
def plan_step(run_dir):
    from . import extract
    catalog = load_catalog()
    eps, brs, cws, skipped = extract.build_endpoints(catalog)
    eps = [e for e in eps if extract.in_scope(e["hints"])]
    brs = [b for b in brs if extract.in_scope(b["hints"])]
    write_json(run_dir / "plan.json", {"at": utc_now(), "catalog": str(config.catalog_path()),
                                       "catalog_verified_on": catalog.get("verified_on"),
                                       "endpoints": eps, "bridges": brs,
                                       "crosswalks": cws, "skipped": skipped})
    # keep the exact catalog the run was planned from, so results stay reproducible
    shutil.copyfile(config.catalog_path(), run_dir / "catalog_snapshot.json")
    log(f"plan: {len(eps)} endpoints in {len({e['graph'] for e in eps})} graphs, {len(brs)} connector patterns, "
        f"{len(cws)} of {len(catalog['verified_crosswalks'])} crosswalks parsed ({len(skipped)} skipped)")
    return catalog


def cmd_pipeline(a):
    from . import build_map, compare, keysets, kgf_profile, patch
    run_dir = config.runs_dir() / a.label
    run_dir.mkdir(parents=True, exist_ok=True)
    steps = ["plan", "profile", "keysets", "map", "report", "explore"] if a.step == "all" else [a.step]
    log(f"run folder: {run_dir}")

    if "plan" in steps or not (run_dir / "plan.json").exists():
        plan_step(run_dir)
    p = read_json(run_dir / "plan.json")
    if a.only:
        keep = {g.strip() for g in a.only.split(",")}
        p["endpoints"] = [e for e in p["endpoints"] if e["graph"] in keep]
        p["bridges"] = [b for b in p["bridges"] if b["graph"] in keep]
        log(f"--only: {len(p['endpoints'])} endpoints, {len(p['bridges'])} connector patterns in {sorted(keep)}")
    catalog = read_json(run_dir / "catalog_snapshot.json") or load_catalog()

    if "profile" in steps:
        log("profile: KGF releases, namespace inventories, federation versions")
        graphs = {e["graph"] for e in p["endpoints"]} | {b["graph"] for b in p["bridges"]}
        write_json(run_dir / "profile.json", kgf_profile.run(graphs))
    if "keysets" in steps:
        log(f"keysets: {len(p['endpoints'])} endpoints, {len(p['bridges'])} connector patterns (cap {a.cap:,})")
        before = read_json(run_dir / "keysets_state.json", {}).get("meter_total", {"requests": 0, "bytes": 0, "seconds": 0})
        st = keysets.run(run_dir, p["endpoints"], p["bridges"], cap=a.cap, timeout=a.timeout,
                         sleep=a.sleep, resume=not a.fresh)
        st["meter_total"] = {k: round(before.get(k, 0) + METER.as_dict()[k], 1) for k in ("requests", "bytes", "seconds")}
        write_json(run_dir / "keysets_state.json", st)
    if a.step == "recanon":
        st = read_json(run_dir / "keysets_state.json")
        n = keysets.recanonicalize(run_dir, p["endpoints"], st)
        log(f"recanon: rebuilt {n} key sets from saved raw values")
        steps = ["map", "report", "explore"]
    if "map" in steps:
        st = read_json(run_dir / "keysets_state.json")
        if not st:
            log("map: run the keysets step first"); return 1
        gk, maps, sources = build_map.load(run_dir, p["endpoints"], p["bridges"], st)
        mp = build_map.compute(gk, maps)
        cmp = compare.run(catalog, p, p["endpoints"], st, mp)
        drafts = patch.run(cmp, p["endpoints"], st, sources)
        write_json(run_dir / "map.json", mp)
        write_json(run_dir / "comparison.json", cmp)
        write_json(run_dir / "catalog_additions_draft.json", drafts)
        log("map: " + json.dumps(cmp["headline"]))
    if "report" in steps:
        from . import report
        log(f"report: {report.run(run_dir)}")
    if "explore" in steps:
        from . import explorer
        log(f"explorer: {explorer.run(run_dir)}")
    if a.step == "verify":
        from . import verify
        st = read_json(run_dir / "keysets_state.json")
        log("verify: " + json.dumps(verify.run(run_dir, p["endpoints"], st, timeout=a.timeout)))
    if a.step == "diff":
        from . import diff
        if not a.against:
            log("diff needs --against <earlier label>"); return 1
        out = diff.run(config.runs_dir() / a.against, run_dir)
        log(json.dumps(out["summary"], indent=1))
    return 0


# ---------------------------------------------------------------- entry point
def build_parser():
    ap = argparse.ArgumentParser(prog="ocm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--home", help="folder for downloads and results (default ./ocm-data, or $OCM_HOME)")
    ap.add_argument("--version", action="version", version=f"okn-connection-map {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    s = sub.add_parser("check", help="test that this computer can reach the OKN services")
    s.add_argument("--offline", action="store_true", help="skip the two network tests")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("fetch-catalog", help="download MCP-OKN's crosswalk catalog")
    s.add_argument("--url", help=f"default: {config.DEFAULT_CATALOG_URL}")
    s.set_defaults(fn=cmd_fetch_catalog)

    s = sub.add_parser("strategy", help="what MCP-OKN's get_join_strategy answers for a pair today")
    s.add_argument("graph_a", nargs="?")
    s.add_argument("graph_b", nargs="?")
    s.add_argument("--all", action="store_true", help="count the answers over every pair of graphs")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_strategy)

    s = sub.add_parser("paths", help="how two graphs connect, with evidence (ocm paths --help)", add_help=False)
    s.set_defaults(fn=None, delegate="paths")
    s = sub.add_parser("demo-page", help="write join_paths_demo.html for a run", add_help=False)
    s.set_defaults(fn=None, delegate="demo-page")
    s = sub.add_parser("mcp", help="serve find_join_paths over MCP (stdio)", add_help=False)
    s.set_defaults(fn=None, delegate="mcp")

    s = sub.add_parser("sparql", help="run a read-only SPARQL query against FRINK and show or save the rows")
    s.add_argument("query", nargs="?", help="the query text, in quotes")
    s.add_argument("--file", nargs="+", help="one or more .rq files (e.g. examples/queries/*.rq)")
    s.add_argument("--out", help="save all rows to this CSV file (single query only)")
    s.add_argument("--limit", type=int, default=10, help="rows to print")
    s.add_argument("--timeout", type=float, default=180.0)
    s.set_defaults(fn=cmd_sparql)

    s = sub.add_parser("kgf", help="list what FRINK's KGF service serves (releases, sizes, links)")
    s.add_argument("dataset", nargs="?", help="one dataset id, to print its full entry")
    s.set_defaults(fn=cmd_kgf)

    s = sub.add_parser("use-sample", help="copy the included sample run into the working folder")
    s.set_defaults(fn=cmd_use_sample)

    s = sub.add_parser("followup", help="which of a run's findings the catalog has added since")
    s.add_argument("--label", help="run to check (default: the latest)")
    s.add_argument("--top", type=int, default=25, help="rows to print")
    s.set_defaults(fn=cmd_followup)

    for step in PIPELINE:
        s = sub.add_parser(step, help={"all": "compute a full run: plan, profile, keysets, map, report, explore",
                                       "plan": "offline: split catalog queries into per-graph patterns",
                                       "profile": "live, ~40 requests: releases and namespace inventories",
                                       "keysets": "live: read each graph's identifiers once (resumable)",
                                       "map": "offline: overlaps, reach, catalog comparison, draft entries",
                                       "report": "offline: report.html",
                                       "explore": "offline: explorer.html",
                                       "verify": "live: spot-check new and refused connections",
                                       "recanon": "offline: re-apply identifier rules to saved raw values",
                                       "diff": "offline: what changed between two runs"}[step])
        s.add_argument("--label", default=str(date.today()), help="name of the run folder (default: today's date)")
        s.add_argument("--against", help="earlier label, for diff")
        s.add_argument("--cap", type=int, default=500_000, help="largest identifier set downloaded per pattern")
        s.add_argument("--timeout", type=float, default=120.0, help="seconds per query")
        s.add_argument("--sleep", type=float, default=0.5, help="pause between queries, to be gentle on FRINK")
        s.add_argument("--only", help="comma-separated graphs, for a quick trial (e.g. nde,rdkg,ubergraph)")
        s.add_argument("--fresh", action="store_true", help="ignore saved progress for this label")
        s.set_defaults(fn=cmd_pipeline, step=step)
    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # global --home may come first; pull it out before delegating
    home = None
    if argv[:1] == ["--home"] and len(argv) > 1:
        home, argv = argv[1], argv[2:]
    elif argv[:1] and argv[0].startswith("--home="):
        home, argv = argv[0].split("=", 1)[1], argv[1:]
    config.set_home(home)
    if argv[:1] in (["paths"], ["demo-page"], ["mcp"]):
        cmd, rest = argv[0], argv[1:]
        if cmd == "paths":
            from .join_paths import main as m
        elif cmd == "demo-page":
            from .demo_page import main as m
        else:
            from .mcp_server import main as m
        return m(rest) or 0
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
