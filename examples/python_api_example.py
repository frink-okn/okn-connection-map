"""Use the connection map from your own Python code (no command line needed).

Run from the folder that holds ocm-data/ (after `ocm fetch-catalog` and `ocm use-sample`),
or point OCM_HOME at it:

    python examples/python_api_example.py
"""
from okn_connection_map import config, join_paths, strategy
from okn_connection_map.common import load_catalog

# 1. What MCP-OKN's get_join_strategy answers today (offline, from the catalog)
catalog = load_catalog()
answer = strategy.join_strategy(catalog, "geoconnex", "ruralkg")
print("get_join_strategy(geoconnex, ruralkg) ->", answer["status"])

# 2. What the computed map says, with evidence (latest run in ocm-data/runs/)
m = join_paths.load()                       # or join_paths.load("2026-10-15c")
result = m.find_join_paths("geoconnex", "ruralkg")
print("find_join_paths verdict:", result["verdict"])
for route in result.get("direct_routes", []):
    print(f"  shares {route['shared_identifiers']:,} {route['meaning']}")

# 3. Everything one graph reaches, strongest first
for row in m.connections_of("nde")["connects_to"][:5]:
    print("  nde ->", row["graph"], row["shared"], "today:", row["today"])

# 4. Optional: re-check the evidence against the live federation (needs network access to apps.okn.us)
# for check in join_paths.run_live(result):
#     print(check)

print("\nWorking folder:", config.home())
