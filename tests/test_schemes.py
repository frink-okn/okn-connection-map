"""Identifier rules: different spellings of the same thing must become one standard form,
and look-alike strings must not be matched."""
import unittest

from okn_connection_map.schemes import canon_any, label_key


class TestCanonicalForms(unittest.TestCase):
    def test_same_identifier_different_spellings(self):
        self.assertEqual(canon_any("http://purl.obolibrary.org/obo/MONDO_0005015", []), "MONDO:0005015")
        self.assertEqual(canon_any("MONDO:0005015", ["MONDO"]), "MONDO:0005015")
        self.assertEqual(canon_any("https://www.ncbi.nlm.nih.gov/gene/1017", ["Entrez"]), "Entrez:1017")
        self.assertEqual(canon_any("50-00-0", ["CAS"]), "CAS:50-00-0")
        self.assertEqual(canon_any("http://identifiers.org/hgnc/HGNC:5", ["HGNC"]), "HGNC:5")

    def test_geography(self):
        self.assertEqual(canon_any("19104", ["ZIP5"]), "ZIP5:19104")
        self.assertEqual(canon_any("9104", ["ZIP5"]), "ZIP5:09104")          # leading zero restored
        self.assertEqual(canon_any("https://datacommons.org/browser/geoId/37183", ["county_FIPS"]),
                         "county_FIPS:37183")

    def test_look_alikes_are_rejected(self):
        # a journal DOI that happens to contain "rs12345" is not a dbSNP variant
        self.assertIsNone(canon_any("https://doi.org/10.3390/rs12345", ["dbSNP"]))
        self.assertEqual(canon_any("rs12345", ["dbSNP"]), "dbSNP:rs12345")
        # a 5-digit number is not a 2-digit state code
        self.assertIsNone(canon_any("22848", ["state_FIPS"]))

    def test_names_are_normalized_separately(self):
        self.assertEqual(label_key("  ALACHUA   county "), "LABEL:alachua county")


if __name__ == "__main__":
    unittest.main()
