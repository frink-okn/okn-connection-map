# 09 · Limits and roadmap

## Current limits

| Limit | Effect | Planned fix |
|---|---|---|
| Only identifier types the catalog already uses (biomedical, geographic) | Joins on other kinds of keys are not found | Read KGF namespace inventories (`profile.json`) to propose new types |
| 29 of 193 catalog queries are not split (UNION, VALUES, several graphs in one block) | Some graphs have fewer patterns than they could | Extend `sparqlsplit.py` |
| Identifier sets above 500,000 values are not downloaded | 16 patterns marked `too_large`; some pairs are "not measured" | KGF hashed key sets (one download per graph, no cap) |
| Mapping graphs: Ubergraph and Wikidata | Routes through other mappers are not counted | Add Babel (the catalog now uses it for 29 crosswalks) |
| Shared identifiers, not meaning | A join can be possible but not useful for a given question | Agent evaluation (below) |
| Sample run from October 2026 | Releases have changed since | Run `ocm all` again; Option D in [06](06_mcp_integration.md) |

## Roadmap

1. **Babel as a third mapping graph**, beside Ubergraph and Wikidata.
2. **KGF key sets** as the input to `keysets`, when served.
3. **Per-release refresh** with a published diff (Option D).
4. **Agent evaluation:** a fixed set of cross-graph questions, answered by an agent with `get_join_strategy` alone versus with `find_join_paths`, measuring how many become answerable and at what query cost.
5. **Budgeted path planning:** given a question and a query budget, choose the path (direct, through a mapping graph, or two hops) that most likely answers it.
