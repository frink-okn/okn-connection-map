# 04 · Running the pipeline

A **run** is one complete measurement of the federation, saved under `ocm-data/runs/<label>/`. Pick any label; a date is a good habit.

```bash
ocm all --label 2026-12-01                                   # every step
ocm all --label quick --only nde,rdkg,spoke-okn,ubergraph    # a trial on a few graphs
```

`all` runs `plan → profile → keysets → map → report → explore`. Each step can also be run on its own with the same `--label`.

## The steps

| Step | Network? | Time (full run) | What it does |
|---|---|---|---|
| `plan` | none | seconds | Reads the catalog and splits each crosswalk query into per-graph **patterns** (one graph's half of a join) and **connector patterns** (a mapping graph's translation, e.g. Ubergraph DOID→MONDO). Saves a copy of the catalog as `catalog_snapshot.json`, so the run can be reproduced. |
| `profile` | about 40 small requests | 1–2 min | Each graph's current KGF release, size and namespace inventory, plus the version the federation reports (okn-void). |
| `keysets` | about 400 requests, about 320 MB | 90–100 min | Reads each pattern's distinct values once (under `--cap`) and rewrites them into standard identifiers. Resumable. |
| `map` | none | about 1 min | Intersects every pair of graphs per identifier type, adds reach through mapping graphs, compares with the catalog, and drafts catalog entries. |
| `report` | none | seconds | `report.html` |
| `explore` | none | seconds | `explorer.html` |
| `verify` | about 5 queries per connection | 10–20 min | Spot-checks every connection the catalog lacks or refuses (plus 10 known ones as a control): samples shared identifiers, checks live that both graphs have them, and fetches their names. |
| `recanon` | none | about 1 min | Re-applies the identifier rules to the saved raw values (`raw/`), then rebuilds map, report and explorer. Use it after improving `schemes.py`, instead of downloading again. |
| `diff` | none | seconds | What changed between two runs (`--against <older label>`) |

After a run, these work offline:
```bash
ocm paths A B             # one pair, with evidence
ocm paths A               # everything graph A reaches
ocm demo-page --label L   # join_paths_demo.html
ocm followup --label L    # which of the run's findings the (newly fetched) catalog has added since
```

## Options

| Option | Default | Meaning |
|---|---|---|
| `--label` | today's date | Name of the run folder |
| `--only a,b,c` | all graphs | Limit the run to these graphs (include `ubergraph` to get mapping routes) |
| `--cap` | 500,000 | Largest set of values downloaded per pattern; larger ones are marked "awaiting key sets" |
| `--timeout` | 120 s | Per query |
| `--sleep` | 0.5 s | Pause between queries |
| `--fresh` | off | Ignore saved progress for this label and start again |
| `--home` | `./ocm-data` | Working folder (before the command: `ocm --home D:\okn all ...`) |

## How a catalog query becomes per-graph patterns

Take this crosswalk query (A32, NDE × rdkg):

```sparql
SELECT (COUNT(DISTINCT ?m) AS ?n) WHERE {
  { SELECT DISTINCT ?m WHERE { GRAPH <…/kg/rdkg> { ?m a <https://w3id.org/biolink/vocab/Disease> } } }
  GRAPH <…/kg/nde> { ?ds <http://schema.org/healthCondition> ?m }
}
```

`plan` keeps each `GRAPH` block as a separate pattern: *rdkg's diseases* and *NDE's health conditions*. `keysets` reads each one once. Every pair of graphs can then be compared using patterns that have already been tested in a verified crosswalk, even pairs that no crosswalk joins directly. This is why `ocm paths` can say *"nde's half reuses the pattern of crosswalk A4, rdkg's half reuses C8"*.

Queries that combine several graphs in one block, or use `UNION` or `VALUES`, are skipped for now. 29 of 193 were skipped in October 2026, and `plan.json` lists them.

## When to run again

- **After a graph is re-released.** `ocm kgf` shows current releases, and `profile.json` records the ones a run measured.
- **After the catalog changes.** Run `ocm fetch-catalog`, then `ocm followup` (no new run needed).
- **After improving identifier rules.** Use `ocm recanon --label L` (no new download).

Then compare the two runs:
```bash
ocm diff --label 2026-12-01 --against 2026-10-15c
```
