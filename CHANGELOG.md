# Changelog

## 0.2.0 (November 2026): first public version for review

- Installable package with one command, `ocm` (`pip install -e .`); still standard library only.
- All paths and service addresses are configurable (`--home`, `OCM_HOME`, `OCM_CATALOG`, ...); no dependence on a particular folder layout.
- `ocm fetch-catalog` downloads MCP-OKN's crosswalk catalog; each run keeps a snapshot of the catalog it used.
- `ocm strategy`: MCP-OKN's `get_join_strategy` rules applied offline (matched the live tool on 903 of 903 audited pairs).
- `ocm followup`: which of a run's findings the current catalog has added since.
- `ocm check`, `ocm sparql`, `ocm kgf`, `ocm use-sample` for first-time users.
- MCP server (`ocm mcp`) with `find_join_paths`, `connections_of`, `list_graphs`.
- Sample results of the 15 October 2026 run; example SPARQL queries; offline test suite; documentation for non-specialists.

## 0.1 (October 2026): research scripts

- Connection map pipeline (plan, profile, keysets, map, report, explorer, verify, recanon, diff) and the first full run of the federation.
