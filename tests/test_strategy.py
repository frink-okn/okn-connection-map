"""The offline copy of MCP-OKN's get_join_strategy rules."""
import unittest

from okn_connection_map.strategy import join_strategy, status_counts

CATALOG = {
    "verified_on": "2026-01-01",
    "verified_crosswalks": [
        {"id": "X1", "left_kg": "a", "right_kg": "b", "shared_key": "MONDO", "verified_count": 10},
        {"id": "X2", "left_kg": "c", "right_kg": "d", "bridge_kg": "ubergraph", "shared_key": "DOID->MONDO"},
    ],
    "known_non_joins": [
        {"left_kg": "a", "right_kg": "e", "attempted_key": "CAS", "diagnosis": "checked: 0"},
        {"kg": "f", "attempted_key": "S2 cell", "diagnosis": "a note about f alone"},
    ],
}


class TestJoinStrategy(unittest.TestCase):
    def test_verified(self):
        r = join_strategy(CATALOG, "b", "a")
        self.assertEqual(r["status"], "verified")
        self.assertEqual(r["joins"][0]["id"], "X1")

    def test_bridge_graph_counts_as_touching(self):
        self.assertEqual(join_strategy(CATALOG, "c", "ubergraph")["status"], "verified")

    def test_pair_specific_refusal(self):
        r = join_strategy(CATALOG, "e", "a")
        self.assertEqual(r["status"], "known_non_join")
        self.assertTrue(r["pair_specific"])

    def test_refusal_inherited_from_single_graph_note(self):
        r = join_strategy(CATALOG, "f", "a")
        self.assertEqual(r["status"], "known_non_join")
        self.assertFalse(r["pair_specific"])
        self.assertEqual(r["non_joins"][0]["about"], "f only")

    def test_verified_wins_over_single_graph_note(self):
        cat = dict(CATALOG, verified_crosswalks=CATALOG["verified_crosswalks"] +
                   [{"id": "X3", "left_kg": "f", "right_kg": "a"}])
        self.assertEqual(join_strategy(cat, "f", "a")["status"], "verified")

    def test_unknown(self):
        self.assertEqual(join_strategy(CATALOG, "b", "d")["status"], "unknown")

    def test_counts(self):
        c = status_counts(CATALOG)
        self.assertEqual(c["pairs"], sum(v for k, v in c.items() if k != "pairs"))


if __name__ == "__main__":
    unittest.main()
