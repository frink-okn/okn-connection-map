# 03 · Getting the data

The tool does not ship or mirror any knowledge graph. It reads what it needs from four public sources, always read-only. This page lists each source, what the tool asks it, and how you can ask the same questions yourself.

| Source | Address | What the tool gets from it | Command |
|---|---|---|---|
| MCP-OKN crosswalk catalog | `https://raw.githubusercontent.com/sbl-sdsc/mcp-okn/main/metadata/crosswalks.json` | Stored crosswalks, known non-joins, and the query of each crosswalk | `ocm fetch-catalog` |
| FRINK federated SPARQL endpoint | `https://apps.okn.us/federation/sparql` | Each graph's identifier values; names of sampled entities; live re-checks | `ocm keysets`, `ocm paths --live`, `ocm sparql` |
| FRINK KGF | `https://apps.okn.us/kgf` | Which release of each graph is served, its size, and its namespace inventory | `ocm profile`, `ocm kgf` |
| okn-void (inside the federation) | graph `https://purl.org/okn/frink/kg/okn-void` | The version and load date the federation reports for each graph | `ocm profile`, `examples/queries/01_…rq` |

The registry of graphs, with human-readable descriptions, is at <https://registry.okn.us/registry/>.

---

## 1. The crosswalk catalog

```bash
ocm fetch-catalog
```

This downloads one JSON file (about 1 MB) into `ocm-data/catalog/crosswalks.json`. If an older copy exists, it is kept beside the new one, named after its `verified_on` date, so you can compare catalog versions.

The parts the tool uses:

| Field | What it is |
|---|---|
| `verified_crosswalks[]` | One entry per stored join: `left_kg`, `right_kg`, optional `bridge_kg` (a mapping graph such as `ubergraph`), `shared_key`, `verified_count`, `verified_on`, and `skeleton_query` (the SPARQL that joins them) |
| `known_non_joins[]` | Notes that a join was tried and failed: about a pair (`left_kg` + `right_kg`) or about a single graph (`kg`) |
| `verified_on` | When the catalog as a whole was last checked |

If GitHub is blocked on your network, download the file in a browser and set `OCM_CATALOG` to its path. To use a different copy, such as a local MCP-OKN clone, run `ocm fetch-catalog --url <address>` or set `OCM_CATALOG`.

## 2. The federated SPARQL endpoint

Every query is a standard SPARQL 1.1 `SELECT`, sent as an HTTP `POST` with the query in a form field named `query`. The tool asks for CSV results, which are several times smaller than JSON.

**From this tool:**
```bash
ocm sparql "SELECT ?g ?v WHERE { GRAPH <https://purl.org/okn/frink/kg/okn-void> { ?g <http://purl.org/pav/version> ?v } } LIMIT 5"
ocm sparql --file examples/queries/02_nde_rdkg_shared_diseases.rq
ocm sparql --file examples/queries/03_geoconnex_ruralkg_shared_counties.rq --out counties.csv
```

**With curl** (any system):
```bash
curl -s -X POST https://apps.okn.us/federation/sparql \
     -H "Accept: text/csv" \
     --data-urlencode "query=SELECT (COUNT(*) AS ?n) WHERE { GRAPH <https://purl.org/okn/frink/kg/nde> { ?s ?p ?o } }"
```

**From Python** (standard library):
```python
import urllib.parse, urllib.request
q = "SELECT ?g ?v WHERE { GRAPH <https://purl.org/okn/frink/kg/okn-void> { ?g <http://purl.org/pav/version> ?v } }"
req = urllib.request.Request("https://apps.okn.us/federation/sparql",
                             data=urllib.parse.urlencode({"query": q}).encode(),
                             headers={"Accept": "text/csv"})
print(urllib.request.urlopen(req, timeout=120).read().decode()[:500])
```

A query reads one graph when its pattern is wrapped in `GRAPH <https://purl.org/okn/frink/kg/<short name>> { ... }`. A cross-graph join puts two such blocks in one query; see the files in [`examples/queries/`](../examples/queries).

### How `ocm keysets` reads identifiers

For each **per-graph pattern** (one graph's half of a catalog crosswalk query; see [04](04_running_the_pipeline.md)):

1. It sends one `COUNT(DISTINCT ...)` query, to learn how many values the pattern has.
2. If that is at most the cap (`--cap`, default 500,000), it sends one `SELECT DISTINCT ...` and saves the values to `raw/<pattern>.txt.gz`.
3. It rewrites each value into its standard form and saves the result to `keys/<pattern>.txt.gz`.
4. Mapping-graph patterns (Ubergraph DOID→MONDO, for example) are read the same way into `bridges/<pattern>.json`.

Progress is saved after every pattern, so an interrupted run continues where it stopped. The full run of October 2026 made 424 requests, downloaded 319 MB and took 102 minutes, with a 0.5-second pause between requests (`--sleep`).

**Etiquette.** The federation is shared by many teams. For experiments, use `--only` to limit a run to a few graphs. Keep `--sleep` at 0.5 seconds or more, and avoid running several full runs at once.

## 3. KGF: releases and namespace inventories

```bash
ocm kgf                 # every dataset KGF serves: id, current release, number of statements, available links
ocm kgf nde             # one dataset's full entry, including the addresses of its other resources
```

The tool reads the KGF index (`GET https://apps.okn.us/kgf` with `Accept: application/json`). It takes `datasets[].id`, `current` (the release), `triples` and `links.summary`. For each graph it then reads the summary as JSON (`?format=json`), which lists the identifier namespaces KGF found, with counts by role (subject or object). These go into `profile.json`.

**Downloading a whole graph.** This tool never needs to, but you may want to for your own analysis. The links that `ocm kgf <dataset>` prints are KGF's own addresses for that release; use the ones KGF offers for downloads. For a part of a graph, a SPARQL `CONSTRUCT` or `SELECT` through the federated endpoint is usually simpler. Please check the FRINK/KGF documentation for current download formats and limits before fetching large files.

### KGF's hashed key sets

When KGF builds a release, it also computes each graph's set of identifiers as 64-bit **XXH64 hashes** (seed 0, over the exact bytes of each IRI), split by role (only subject, only object, both). Comparing two graphs' hash sets gives their overlap without any SPARQL. `kgf_hash.py` reproduces the hash:

```bash
python -m okn_connection_map.kgf_hash http://purl.obolibrary.org/obo/MONDO_0004979
```

Once KGF serves these sets for download, only the `keysets` step of this tool changes. The rest of the pipeline stays the same, and the 500,000 cap no longer applies.

## 4. okn-void: what the federation reports about each graph

```bash
ocm sparql --file examples/queries/01_graphs_and_versions.rq
```

This lists each graph with `pav:version` and `pav:lastUpdatedOn`. The tool stores these beside the KGF release in `profile.json`, so every number in a run can be tied to the release it was measured on.
