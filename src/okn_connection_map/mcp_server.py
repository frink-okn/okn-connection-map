"""A minimal MCP server (stdio) that serves the computed connection map to any MCP client.

Tools:
  find_join_paths(graph_a, graph_b)  how two graphs connect: today's get_join_strategy answer
                                     beside every route the data support, with evidence
  connections_of(graph)              every graph this one reaches, strongest first
  list_graphs()                      graphs in the map, with releases

Standard library only (JSON-RPC 2.0 over stdin/stdout, MCP protocol 2024-11-05), so it runs
anywhere the connection-map tool runs and can sit beside MCP-OKN without changing it.

Run:      ocm mcp [--label 2026-10-15c]        (or: python -m okn_connection_map mcp)
Client config (Claude Desktop, Claude Code, any MCP client): see docs/06_mcp_integration.md
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, join_paths

PROTOCOL = "2024-11-05"
TOOLS = [
    {"name": "find_join_paths",
     "description": ("How two FRINK knowledge graphs connect, computed from the identifiers each graph "
                     "actually holds at its current release. Returns MCP-OKN get_join_strategy's current "
                     "answer for the pair beside every supported route: shared identifiers per scheme "
                     "(MONDO, NCBI Gene, CAS, ZIP, FIPS, ...), extra reach through mapping graphs "
                     "(Ubergraph, Wikidata), two-hop routes through a third graph, sample identifiers with "
                     "their names in both graphs, and small queries that return them live. Never answers "
                     "'cannot join' for graphs whose identifier sets were not fully read."),
     "inputSchema": {"type": "object", "required": ["graph_a", "graph_b"],
                     "properties": {"graph_a": {"type": "string", "description": "FRINK short name, e.g. nde"},
                                    "graph_b": {"type": "string", "description": "FRINK short name, e.g. rdkg"}}}},
    {"name": "connections_of",
     "description": "Every graph that shares identifiers with the given graph, strongest first, with today's tool status for each pair.",
     "inputSchema": {"type": "object", "required": ["graph"],
                     "properties": {"graph": {"type": "string"}}}},
    {"name": "list_graphs",
     "description": "Graphs covered by the connection map, with the release each was measured on.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def call(m, name, args):
    if name == "find_join_paths":
        return m.find_join_paths(args["graph_a"], args["graph_b"])
    if name == "connections_of":
        return m.connections_of(args["graph"])
    if name == "list_graphs":
        return {"measured_on_run": m.run_dir.name,
                "graphs": [{"graph": g, "release": m.release(g)} for g in m.graphs]}
    raise KeyError(name)


def handle(m, msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", PROTOCOL),
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "okn-connection-map", "version": __version__}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            out = call(m, params.get("name"), params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(out, indent=2)}],
                      "isError": "error" in out}
        except Exception as e:  # report tool errors to the client instead of crashing
            result = {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
    elif method == "ping":
        result = {}
    elif mid is None:  # a notification (e.g. notifications/initialized): no reply
        return None
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ocm mcp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", help="run to serve (default: the latest)")
    a = ap.parse_args(argv)
    m = join_paths.load(a.label)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(m, json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
