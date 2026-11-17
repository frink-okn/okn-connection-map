# 05 · Reading the outputs

## The three pages (open in any browser; no internet needed)

| Page | Question it answers | How to read it |
|---|---|---|
| `report.html` | Across the whole federation, how much of the catalog still holds, and what does it miss? | Headline numbers at the top; a network of graphs; then tables of connections the catalog lists, lacks, or refuses ("do not retry") |
| `explorer.html` | Starting from one graph, what can I reach? | Click a graph on the left. Each row is a graph it shares identifiers with, with counts per identifier type, a badge for what the catalog says, and candidate paths below |
| `join_paths_demo.html` | For one pair: what does the agent hear today, and what do the data show? | Pick a pair (or click a highlighted one). Left: MCP-OKN's answer and the note it rests on. Right: routes, matching names, which verified crosswalks each half reuses, and the live queries |

## Labels used for connections

| Label | Meaning |
|---|---|
| **In the catalog** (`confirmed`) | The catalog already has a crosswalk for this pair |
| **Not in the catalog** (`new`) | The data connect; `get_join_strategy` answers `unknown` |
| **Catalog says "do not retry"** (`contradicts_refusal`) | The data connect; `get_join_strategy` answers `known_non_join` |
| **Names only** (`label_only`) | The graphs share only names (e.g. "Alachua County"), not identifiers. This is weaker evidence: many states have a Washington County |

Labels are computed against the catalog the run used (`catalog_snapshot.json`). To compare with today's catalog, run `ocm fetch-catalog` and then `ocm followup`.

## Files in a run folder

| File | Contents |
|---|---|
| `plan.json` | The per-graph patterns and connector patterns taken from the catalog, and the queries that could not be split |
| `catalog_snapshot.json` | The exact catalog this run was planned from |
| `profile.json` | Per graph: KGF release, statement count, namespace inventory, federation version and load date |
| `keysets_state.json` | Per pattern: status (`ok`, `ok_truncated`, `ok_uncounted`, `empty`, `too_large`, `count_failed`, `download_failed`), counts, identifier types found, time and bytes; totals for the run |
| `keys/*.txt.gz` | The standard-form identifiers per pattern (one per line) |
| `raw/*.txt.gz` | The values exactly as each graph wrote them, kept so rules can be re-applied offline |
| `bridges/*.json` | Mapping-graph translations (e.g. DOID → MONDO through Ubergraph) |
| `map.json` | Overlaps per pair and identifier type (`direct`), and reach per ordered pair including mapping graphs (`reach`) |
| `comparison.json` | Every connection with its label, and every catalog crosswalk marked reproduced / not found now / awaiting key sets / not parsed; the `headline` numbers |
| `catalog_additions_draft.json` | Draft catalog entries, in MCP-OKN's format, for connections the catalog lacks |
| `verify.csv`, `verify_summary.json` | Live spot checks: per sampled identifier, how each graph writes it, whether it was found, and its name |
| `catalog_followup.json` | Written by `ocm followup`: which findings the current catalog has added since, and which are still open |

## The answer of `find_join_paths` (and `ocm paths A B --json`)

```jsonc
{
  "pair": ["geoconnex", "ruralkg"],
  "today_get_join_strategy": {               // what MCP-OKN answers now
    "status": "known_non_join",
    "computed_from": "MCP-OKN rules applied to the catalog",
    "catalog_verified_on": "2026-11-09",
    "stored_crosswalks": [],                  // crosswalks for this pair, if verified
    "refusal_notes": [{"about": "geoconnex only", "attempted_key": "S2 Level-13 cell ...", "diagnosis": "..."}],
    "pair_specific": false                    // false = the refusal rests on a note about one graph
  },
  "releases": {"geoconnex": {"kgf": "v0.0.4", "federation": "v0.0.4", "loaded": "2026-04-02"}, "ruralkg": {...}},
  "measured_on_run": "2026-10-15c",
  "coverage": {"geoconnex": {"patterns": 4, "read": 4, "not_read": 0}, ...},  // were all identifiers read?
  "verdict": "connect",                       // connect | shared names only | not measured | no shared identifiers found
  "direct_routes": [{"scheme": "county_FIPS", "meaning": "county (FIPS)", "shared_identifiers": 3222}],
  "bridged_routes": [],                       // extra identifiers reached through ubergraph / wikidata
  "reach": {"geoconnex -> ruralkg": {"direct": ..., "only_via_connector": ..., "either": ...}, ...},
  "two_hop_routes": [{"via_graph": "spoke-okn", "first_hop": "...", "second_hop": "...", "at_most": 3184}],
  "evidence": [{"identifier": "county_FIPS:39073", "scheme": "county_FIPS",
                "geoconnex": {"as_written": "...", "name": null}, "ruralkg": {"as_written": "...", "name": null}}],
  "evidence_queries": [{"graph": "geoconnex", "scheme": "county_FIPS", "expect": 5,
                        "pattern_from_crosswalks": ["L1-county-fips-geoconnex-spatialkg"], "sparql": "..."}],
  "change_vs_today": "tool refuses a pair the data connect"
}
```

With `--live`, a `live_check` list is added, showing how many sampled identifiers each evidence query returned just now.

**Verdicts, carefully worded:**
- `connect`: shared identifiers were found (directly or through a mapping graph).
- `shared names only`: only names match. Treat this as a lead, not a join.
- `not measured`: some of the graphs' identifiers were too many to download, so no claim is made.
- `no shared identifiers found`: everything was read and nothing is shared, for the identifier types the catalog uses at these releases.
