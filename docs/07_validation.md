# 07 · Validation: how we know the answers are right

Each check below says what was tested, how, and the result, with the command to repeat it.

## 1. The "today" answer is MCP-OKN's real answer

`strategy.py` applies MCP-OKN's own rules (from `src/mcp_okn/tools/joins.py` and `crosswalks.py`) to the catalog file:
1. `verified` if any crosswalk touches both graphs;
2. else `known_non_join` if a non-join note names both graphs, or either graph alone;
3. else `unknown`.

**Test:** in September 2026, an audit called the live `get_join_strategy` on all 903 pairs of the graphs then in the catalog. Applied to the same catalog version (26 Sept 2026), `strategy.py` gave the same answer for **903 of 903 pairs**.

**Repeat:** `ocm strategy A B`. With the audit's file present, set `OCM_AUDIT_DIR` to compare.

If MCP-OKN changes its rules, `strategy.py` must be updated to match. The unit tests in `tests/test_strategy.py` describe the expected behaviour.

## 2. The map reproduces the curated catalog

For each stored crosswalk whose two per-graph patterns were both read, the map should find shared identifiers for that pair.

**Result (run 2026-10-15c, catalog of 26 Sept 2026):**

| Outcome | Crosswalks |
|---|---|
| Reproduced | **117 of 122 testable** |
| Not found now | 5: listed in `report.html`. These are candidates for broken or changed joins |
| Awaiting key sets | 31 (one side's identifier set exceeded the download cap) |
| Not parsed (query shape not yet supported) | the remainder of 193 |

## 3. The counts agree with the curators' counts

Where a crosswalk records a `verified_count` (or a later live count), and the map measures the same pair with the same identifier type:

| Agreement | Crosswalks |
|---|---|
| Exactly equal | **62** |
| Within 5% | **14** |
| Differ by more | 9: several join on titles or names rather than identifiers; all are listed in `join_paths_demo.html` for checking |
| **Total compared** | **85** (76 of 85 = 89% within 5%) |

**Repeat:** open `join_paths_demo.html` → "Are the computed numbers right?"

## 4. Every computed join uses an already-verified pattern

The map never invents a query. Each graph's half of a computed join is a pattern taken from a catalog crosswalk that was verified for some pair. `ocm paths A B` names it on the HOW lines, for example:

```
HOW    geoconnex   county_FIPS  pattern reused from catalog crosswalk L1-county-fips-geoconnex-spatialkg
HOW    ruralkg     county_FIPS  pattern reused from catalog crosswalk K2-county-fips
```

## 5. The same entity on both sides

For sampled shared identifiers, `verify` fetches the name each graph gives the entity. Examples for NDE × rdkg:

| Identifier | In NDE | In rdkg |
|---|---|---|
| MONDO:0021545 | myomatous neoplasm | myomatous neoplasm |
| MONDO:0100253 | Roberts-SC phocomelia syndrome | Roberts-SC phocomelia syndrome |
| MONDO:0016168 | cryopyrin-associated periodic syndrome | cryopyrin-associated periodic syndrome |

County codes and CAS numbers often have no name in a graph. For those, the identifier itself plus the count agreement (check 3) is the evidence.

## 6. Live re-check

`ocm paths A B --live` runs, for each graph and identifier type, a small query that must return the sampled identifiers now.

**Result, 11 Nov 2026:**

| Pair | Returned live |
|---|---|
| NDE × rdkg | NDE 6 of 6, rdkg 6 of 6 (MONDO and HP) |
| GeoConnex × RuralKG | 5 of 5 and 5 of 5 (county FIPS) |
| AOP-Wiki × ICE | 6 of 6 and 6 of 6 (CAS and NCBI Gene) |
| **Total** | **34 of 34** |

## 7. Independent confirmation by the catalog's maintainers

Of the 40 identifier connections the October run found outside the catalog, **10 were later added by the maintainers** (catalog of 9 Nov 2026). **8 of the 10 have exactly the count the map computed**:

| Pair | Map, 15 Oct | Catalog |
|---|---|---|
| NDE × rdkg | 2,907 | A32: 2,907 |
| NDE × ProKN (MONDO) | 756 | A33: 756 |
| DIGCFDE × NDE (MONDO) | 158 | A34: 158 |
| MeSH × Tox21 | 1,103 | M8: 1,103 |
| AOP-Wiki × Tox21 | 285 | E4: 285 |
| Tox21 × SOCKG | 55 | ET5: 55 |
| Tox21 × SAWGraph | 11 | ET6: 11 |
| AOP-Wiki × SOCKG | 8 | ET7: 8 |

**Repeat:** `ocm fetch-catalog`, then `ocm followup`.

## 8. Identifier rules are tested

`tests/test_schemes.py` checks that different spellings become one standard form, and that look-alikes are rejected. For example, a journal DOI containing `rs12345` is not a dbSNP variant, and a 5-digit number is not a 2-digit state code. Both errors occurred in an early run, and these tests make sure they stay fixed.

## Known caveats

- The sample's `verify.csv` and `verify_summary.json` come from an earlier version of the spot-check. Its **found / not found** column is unreliable for patterns that build the identifier inside the query, because of a query-ordering bug that has since been fixed. Its names are correct. Re-run `ocm verify --label 2026-10-15c` for fresh values. Check 6 above uses the corrected queries.
- A shared identifier shows two graphs *can* be joined. Whether a particular question across them makes sense is a separate judgement.
