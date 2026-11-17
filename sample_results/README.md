# Sample results: run 2026-10-15c

A complete run of `okn-connection-map` over the FRINK federation, made on 15 October 2026. It lets you try every offline command without a 100-minute run:

```bash
ocm fetch-catalog      # today's catalog, for the "today" answers
ocm use-sample         # copies this folder into ocm-data/runs/
ocm paths nde rdkg
ocm followup
```

| File | What it is |
|---|---|
| `report.html` | Federation-wide findings: open in a browser |
| `explorer.html` | One graph at a time: open in a browser |
| `join_paths_demo.html` | Any two graphs, today's answer vs computed. Built with the catalog of 9 Nov 2026 |
| `comparison.json`, `map.json` | The computed connections and the comparison with the catalog |
| `catalog_additions_draft.json` | Draft catalog entries for connections the catalog lacked |
| `catalog_followup.json` | Which findings the 9 Nov 2026 catalog has added since (10 of 40) and which are still open |
| `plan.json`, `profile.json`, `keysets_state.json` | Patterns used, releases measured, and per-pattern status and cost |
| `verify.csv`, `verify_summary.json` | Live spot checks of sampled identifiers (see the note below) |
| `catalog_snapshot.json` | The MCP-OKN catalog (26 Sept 2026) this run was compared with |

**Run size:** 34 graphs profiled, 184 per-graph patterns, 424 requests, 319 MB, 102 minutes.

**Not included:** the downloaded identifier files (`raw/`, `keys/`, `bridges/`, about 63 MB). Without them, `map` and `recanon` cannot be re-run on this sample, but everything else works. Compute your own run to get them.

**Labels:** `report.html` and `explorer.html` label connections against the catalog of 26 Sept 2026. Several connections shown there as missing or refused have since been added; see `catalog_followup.json`.

**Note on `verify`:** these spot-check files come from an earlier version of `verify.py`. Their found / not-found column is unreliable for some patterns, because of a query-ordering bug that has since been fixed; the names are correct. The live re-check of 11 Nov 2026 (34 of 34 found) used the corrected queries; see [docs/07_validation.md](../docs/07_validation.md).
