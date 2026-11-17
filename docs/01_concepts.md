# 01 · Concepts in plain words

This page explains the ideas behind the tool without assuming a computer-science background. If you know knowledge graphs and SPARQL, skip to [04 Running the pipeline](04_running_the_pipeline.md).

## Knowledge graph

A **knowledge graph** stores facts as small statements of the form *thing → relationship → thing*:

```
dataset 123        → studies condition →   asthma
asthma             → has phenotype     →   wheezing
Durham County, NC  → is in state       →   North Carolina
```

Each "thing" has an **identifier**, a precise name that does not depend on wording. Asthma, for example, is `MONDO:0004979` in the MONDO disease ontology.

## Proto-OKN, FRINK and the federation

**Proto-OKN** (Prototype Open Knowledge Network) is an NSF-funded program in which many teams each build a knowledge graph: about diseases and genes, chemicals and toxicity, water, rural communities, courts, manufacturing, and more. **FRINK** (run by RENCI) loads these graphs into one shared service, the **federation**, so a single query can read from several graphs at once. Each graph has a short name such as `nde`, `rdkg`, `spoke-okn` or `ruralkg`, and a full address of the form `https://purl.org/okn/frink/kg/<short name>`.

## Join

A **join** connects two graphs through something they both mention. If NDE says *"dataset 123 studies `MONDO:0004979`"* and rdkg says *"`MONDO:0004979` is caused by gene X"*, a question can travel from datasets to genes, but only because both graphs use the same identifier for asthma.

Joins fail silently when graphs spell the same identifier differently. Here are three spellings of one disease:

```
http://purl.obolibrary.org/obo/MONDO_0004979
https://identifiers.org/mondo:0004979
MONDO:0004979
```

The tool rewrites each value into one **standard form** (`MONDO:0004979`) before comparing. The rules for each kind of identifier (diseases, genes, chemicals, ZIP codes, county codes, ...) are in `schemes.py`.

## Mapping graph (connector)

Sometimes two graphs describe the same thing with *different* identifier systems: one uses the Disease Ontology (`DOID:…`), the other uses MONDO. A **mapping graph** such as **Ubergraph** or **Wikidata** records that `DOID:2841` and `MONDO:0004979` are the same disease, so the join can go *through* it. The tool reports these routes separately, as "through ubergraph".

## Crosswalk and the crosswalk catalog

A **crosswalk** is a stored, tested join rule for one pair of graphs: which identifier they share, the query that joins them, and how many matches it returned when it was checked. **MCP-OKN** keeps about 270 crosswalks in a file called `crosswalks.json`, the **crosswalk catalog**. It is curated by hand.

The catalog also stores **known non-joins**: notes saying a join was tried and failed. Some notes are about a pair ("A and B share no CAS numbers"). Others are about a single graph ("graph F's S2 cells match nothing"). MCP-OKN applies a single-graph note to *every* pair that includes that graph.

## Path

A **path** is the chain of graphs an answer follows. A direct path joins two graphs on a shared identifier. Other paths go through a mapping graph, or through a third graph (two hops).

## SPARQL

**SPARQL** is the query language for knowledge graphs, much as SQL is for tables. The federation answers SPARQL queries at `https://apps.okn.us/federation/sparql`. This tool sends only **read** queries (`SELECT`), so it never changes anything. Example queries are in [`examples/queries/`](../examples/queries), and you can run them with `ocm sparql --file ...`.

## KGF

**KGF** is FRINK's service for describing graph releases: which version of each graph is served, how many statements it has, and which identifier namespaces it uses. KGF also builds **hashed key sets**: compact fingerprints of every identifier in a release. Once those can be downloaded, this tool can compare graphs without querying them at all.

## MCP and AI agents

An **AI agent** is an AI assistant (such as Claude) that can call tools to get information. **MCP** (Model Context Protocol) is the standard plug that connects an agent to a tool. **MCP-OKN** is the MCP server that lets agents query the OKN federation. Its tool `get_join_strategy(graph_a, graph_b)` tells the agent whether two graphs can be joined, and its three answers decide what the agent does next:

| Answer | Agent's next step |
|---|---|
| `verified` | use the stored crosswalk |
| `unknown` | try to discover a join itself |
| `known_non_join` | stop: "do not retry" |

This repository adds an MCP tool, `find_join_paths`, which answers the same question from the computed map and includes the evidence.

## Release

Graphs are updated from time to time, and each update is a **release** with a version such as `v0.0.3`. A join that works on one release may break on the next. The tool records the release it measured for each graph, so you can tell when an answer may be out of date, and `ocm diff` shows what changed between two runs.
