"""Demo: talk to the connection-map MCP server exactly as an MCP client (Claude, an agent) would.

Starts the server (`ocm mcp`), does the MCP handshake, lists its tools, and asks how pairs
connect. For each pair it prints what MCP-OKN's get_join_strategy answers today beside what
the computed map answers. Run it from the folder that holds ocm-data/ (or set OCM_HOME).

  python examples/demo_mcp_session.py                      # default pairs
  python examples/demo_mcp_session.py nde rdkg scales sudokn
  python examples/demo_mcp_session.py --raw nde rdkg       # also print the raw JSON-RPC messages
"""
from __future__ import annotations

import json
import subprocess
import sys

DEFAULT = ["geoconnex", "ruralkg", "biobricks-aopwiki", "biobricks-ice", "nde", "rdkg", "spoke-okn", "nde"]


class Client:
    def __init__(self, raw=False, label=None):
        cmd = [sys.executable, "-m", "okn_connection_map", "mcp"] + (["--label", label] if label else [])
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.raw, self.n = raw, 0

    def send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self.n += 1
            msg["id"] = self.n
        line = json.dumps(msg)
        if self.raw:
            print("  -> " + line[:300])
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        if notify:
            return None
        reply = json.loads(self.p.stdout.readline())
        if self.raw:
            print("  <- " + json.dumps(reply)[:300] + ("..." if len(json.dumps(reply)) > 300 else ""))
        return reply

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


def main():
    args = [a for a in sys.argv[1:] if a != "--raw"]
    pairs = args or DEFAULT
    c = Client(raw="--raw" in sys.argv)
    init = c.send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "demo", "version": "0"}})["result"]
    c.send("notifications/initialized", notify=True)
    tools = c.send("tools/list")["result"]["tools"]
    print(f"Connected to MCP server '{init['serverInfo']['name']}' {init['serverInfo']['version']}, "
          f"protocol {init['protocolVersion']}. Tools: {', '.join(t['name'] for t in tools)}\n")
    for a, b in zip(pairs[0::2], pairs[1::2]):
        r = c.send("tools/call", {"name": "find_join_paths", "arguments": {"graph_a": a, "graph_b": b}})
        res = json.loads(r["result"]["content"][0]["text"])
        t = res["today_get_join_strategy"]
        print(f"=== {a} x {b} " + "=" * max(0, 60 - len(a) - len(b)))
        print(f"  MCP-OKN get_join_strategy today : {t['status']}")
        for n in t.get("stored_elsewhere", []):
            print(f"     (catalog entry {n['in_entry']} stores {n['count']} for this pair, not returned by the tool)")
        for n in t["refusal_notes"][:1]:
            print(f"     refusal rests on a note about {n['about']}: \"{n['attempted_key']}\"")
        print(f"  find_join_paths (computed)      : {res['verdict']}")
        for d in res.get("direct_routes", [])[:3]:
            print(f"     {d['shared_identifiers']:>7,} shared {d['meaning']}")
        for d in res.get("bridged_routes", [])[:2]:
            print(f"     {d['extra_identifiers']:>7,} more through {d['through']}")
        ev = [s for s in res.get("evidence", []) if s[a]["name"] or s[b]["name"]][:2]
        for s in ev:
            print(f"     e.g. {s['identifier']}: '{s[a]['name'] or '-'}' in {a}, '{s[b]['name'] or '-'}' in {b}")
        if res.get("change_vs_today"):
            print(f"  => {res['change_vs_today']}")
        print()
    c.close()


if __name__ == "__main__":
    main()
