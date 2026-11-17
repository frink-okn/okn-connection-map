"""End to end on the included sample run, offline: find_join_paths and the MCP protocol."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from okn_connection_map import config, join_paths, mcp_server

SAMPLE = Path(__file__).resolve().parents[1] / "sample_results" / "2026-10-15c"


@unittest.skipUnless(SAMPLE.exists(), "sample_results not present")
class TestSampleRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        shutil.copytree(SAMPLE, Path(cls.tmp) / "runs" / SAMPLE.name)
        cls._env = os.environ.pop("OCM_CATALOG", None)
        config.set_home(cls.tmp)                 # no catalog in this home: the run's snapshot is used
        join_paths.load.cache_clear()
        cls.m = join_paths.load(SAMPLE.name)

    @classmethod
    def tearDownClass(cls):
        config.set_home(None)
        if cls._env:
            os.environ["OCM_CATALOG"] = cls._env
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_refused_pair_connects(self):
        r = self.m.find_join_paths("geoconnex", "ruralkg")
        self.assertEqual(r["today_get_join_strategy"]["status"], "known_non_join")
        self.assertEqual(r["verdict"], "connect")
        self.assertEqual({d["scheme"]: d["shared_identifiers"] for d in r["direct_routes"]}["county_FIPS"], 3222)
        self.assertTrue(r["evidence_queries"])

    def test_unknown_graph_is_an_error_not_a_crash(self):
        self.assertIn("error", self.m.find_join_paths("no-such-graph", "nde"))

    def test_mcp_handshake_and_call(self):
        init = mcp_server.handle(self.m, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                          "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "okn-connection-map")
        self.assertIsNone(mcp_server.handle(self.m, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
        tools = mcp_server.handle(self.m, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual({t["name"] for t in tools["result"]["tools"]},
                         {"find_join_paths", "connections_of", "list_graphs"})
        call = mcp_server.handle(self.m, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                          "params": {"name": "find_join_paths",
                                                     "arguments": {"graph_a": "nde", "graph_b": "rdkg"}}})
        self.assertFalse(call["result"]["isError"])
        self.assertEqual(json.loads(call["result"]["content"][0]["text"])["verdict"], "connect")


if __name__ == "__main__":
    unittest.main()
