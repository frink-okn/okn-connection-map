# 06 · MCP integration

This page shows how to give an AI agent the `find_join_paths` tool, and how the computed map could be built into MCP-OKN itself.

## What the server offers

`ocm mcp` starts an MCP server that talks over standard input and output ("stdio"), using JSON-RPC 2.0 and MCP protocol version `2024-11-05`. It is written with the Python standard library only.

| Tool | Arguments | Returns |
|---|---|---|
| `find_join_paths` | `graph_a`, `graph_b` (FRINK short names, e.g. `nde`, `rdkg`) | The full answer described in [05](05_reading_the_outputs.md#the-answer-of-find_join_paths-and-ocm-paths-a-b---json) |
| `connections_of` | `graph` | Every graph sharing identifiers with it, strongest first, each with today's `get_join_strategy` status |
| `list_graphs` | none | Graphs in the map, with the release each was measured on |

The server serves the **latest run** in the working folder; add `--label <run>` to pin one. It needs a computed run (or `ocm use-sample`) and, for the "today" part, the catalog (`ocm fetch-catalog`).

## Connect a client

### Claude Desktop

1. Open Claude Desktop → **Settings** → **Developer** → **Edit Config**. This opens `claude_desktop_config.json`:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Add the server. Use the **full path** to `ocm` inside your environment, and point `OCM_HOME` at your `ocm-data` folder:

   Windows ([`examples/claude_desktop_config.json`](../examples/claude_desktop_config.json)):
   ```json
   {
     "mcpServers": {
       "okn-connection-map": {
         "command": "C:\\Users\\YOUR_NAME\\okn-connection-map\\.venv\\Scripts\\ocm.exe",
         "args": ["mcp"],
         "env": { "OCM_HOME": "C:\\Users\\YOUR_NAME\\okn-connection-map\\ocm-data" }
       }
     }
   }
   ```
   With Anaconda, the command is `C:\\Users\\YOUR_NAME\\anaconda3\\envs\\okn\\Scripts\\ocm.exe`. To find the right path, run `where ocm` (Windows) or `which ocm` (macOS/Linux) with the environment active.

   macOS/Linux: [`examples/claude_desktop_config_macos_linux.json`](../examples/claude_desktop_config_macos_linux.json).
3. Restart Claude Desktop. The tools appear under the tools (plug) icon.
4. To use it **together with MCP-OKN**, also add the hosted MCP-OKN server, as described in MCP-OKN's README (Settings → Connectors → Add custom connector, URL `https://apps.okn.us/okn-mcp-dev/mcp`). Then ask, for example: *"Which court cases in SCALES come from rural counties in RuralKG? Use find_join_paths before deciding two graphs cannot be joined."*

### Claude Code

```bash
claude mcp add okn-connection-map --env OCM_HOME=/path/to/ocm-data -- /path/to/.venv/bin/ocm mcp
```

### Any other MCP client

Configure a stdio server with the command `ocm` (full path) and the argument `mcp`, and set the environment variable `OCM_HOME`.

### Without any AI client

[`examples/demo_mcp_session.py`](../examples/demo_mcp_session.py) starts the server and talks to it exactly as a client would. Add `--raw` to see every JSON-RPC message:

```bash
python examples/demo_mcp_session.py --raw geoconnex ruralkg
```
```
  -> {"jsonrpc": "2.0", "method": "initialize", ...}
  <- {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "serverInfo": {"name": "okn-connection-map", ...}}}
  -> {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "find_join_paths", "arguments": {"graph_a": "geoconnex", "graph_b": "ruralkg"}}, "id": 3}
=== geoconnex x ruralkg ===
  MCP-OKN get_join_strategy today : known_non_join
     refusal rests on a note about geoconnex only: "S2 Level-13 cell (re-confirm) / ..."
  find_join_paths (computed)      : connect
       3,222 shared county (FIPS)
  => tool refuses a pair the data connect
```

### From Python, without MCP

See [`examples/python_api_example.py`](../examples/python_api_example.py):
```python
from okn_connection_map import join_paths
m = join_paths.load()
print(m.find_join_paths("geoconnex", "ruralkg")["verdict"])
```

---

## Integration options for MCP-OKN

The four options from the README, in more detail. They are independent, so any one can be adopted on its own.

### Option A: side by side (works today)

Run this server next to MCP-OKN, as above. Nothing in MCP-OKN changes. Agents see both `get_join_strategy` and `find_join_paths`. **Trade-off:** the agent has to choose to call the second tool. A line in MCP-OKN's server instructions (for example, *"before treating two graphs as unjoinable, call find_join_paths"*) makes that more likely.

### Option B: catalog maintenance

Each run writes `catalog_additions_draft.json`: connections the catalog lacks, as draft entries with `left_kg`, `right_kg`, `shared_key`, the computed count, the releases, and a runnable query where both graphs spell the identifier the same way. `ocm followup` lists which findings are still open against the latest catalog. A maintainer reviews the drafts like any pull request. The catalog stays curated; the tool only does the searching.

### Option C: a second opinion inside `get_join_strategy`

When the catalog answers `unknown` or `known_non_join`, MCP-OKN could also consult the computed map. If the data connect, it adds the routes and evidence to its answer. The existing statuses stay the same, so current clients are unaffected. A sketch for `src/mcp_okn/tools/joins.py`:

```python
# --- near the top of joins.py
try:
    from okn_connection_map import join_paths as _ocm
    _MAP = _ocm.load()           # latest run under $OCM_HOME (deployed with the server)
except Exception:                # map not installed or not computed: behave exactly as before
    _MAP = None


def _computed_second_opinion(kg_a: str, kg_b: str):
    if _MAP is None:
        return None
    r = _MAP.find_join_paths(kg_a, kg_b)
    if r.get("verdict") != "connect":
        return None
    return {k: r.get(k) for k in ("verdict", "direct_routes", "bridged_routes", "two_hop_routes",
                                  "evidence", "evidence_queries", "releases", "measured_on_run")}


# --- in get_join_strategy, just before returning the known_non_join answer (and the unknown one):
    second = _computed_second_opinion(kg_a, kg_b)
    if second:
        out["computed_map"] = second
        out["note"] += (" However, the computed connection map found shared identifiers for this pair "
                        "at the releases listed in computed_map; run its evidence_queries before relying on it.")
```

**Trade-offs:**
- The map must be refreshed per release (Option D). Otherwise it can be stale in the other direction.
- The map is about 1 MB of JSON per run, without the raw downloads, so it can ship with the server.

### Option D: refresh per release

A scheduled job, for example weekly or when KGF's index shows a new `current` release:

```bash
ocm fetch-catalog
ocm all --label $(date +%F)
ocm diff --label $(date +%F) --against <previous label>
ocm followup
```

It publishes the four outputs: the report, the diff of joins gained, lost or changed, the open findings, and the draft entries. With KGF's hashed identifier sets downloadable, the `keysets` step becomes one download per graph, and graphs above the current cap get measured too.

## What we'd ask of the OKN team

1. **Feedback** on whether `find_join_paths` answers are useful to agents, and on Option C's wording.
2. **KGF key-set downloads**, which remove the download cap and most of the run time.
3. **A place to run** Option D, and a decision on where its outputs should be published.
