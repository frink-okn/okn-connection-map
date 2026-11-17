"""Identifier schemes: recognise a value's scheme and reduce it to one canonical form.

A canonical key is "SCHEME:local-id" (e.g. "MONDO:0005015", "ZIP5:19104"), so keys from
different schemes can never collide and keys from different IRI spellings of the same
identifier (http vs https, identifiers.org vs ensembl.org, MONDO_ vs MONDO:) compare equal.
"""
from __future__ import annotations

import re

# family: 'bio' or 'geo' (the first version's scope), 'other' otherwise.
# Patterns run on the lexical value (an IRI or a literal) and capture the local id.
_SCHEMES: list[tuple[str, str, str]] = [
    ("MONDO", "bio", r"MONDO[_:](\d{7})"),
    ("DOID", "bio", r"DOID[_:](\d+)"),
    ("HP", "bio", r"(?<![A-Z])HP[_:](\d{7})"),
    ("UBERON", "bio", r"UBERON[_:](\d{7})"),
    ("CL", "bio", r"(?<![A-Z])CL[_:](\d{7})"),
    ("CHEBI", "bio", r"CHEBI[_:](\d+)"),
    ("NCBITaxon", "bio", r"NCBITaxon[_:](\d+)"),
    ("GO", "bio", r"(?<![A-Z])GO[_:](\d{7})"),
    ("EFO", "bio", r"EFO[_:](\d+)"),
    ("OMIM", "bio", r"(?i:omim)[/:_.](?:MIM:)?(\d{6})"),
    ("Orphanet", "bio", r"(?i:orphanet|orpha)[/:_.](\d+)"),
    ("UMLS", "bio", r"(?:UMLS[:/_]|/)(C\d{7})\b"),
    ("MeSH", "bio", r"(?:mesh[/:]|MESH:)([DC]\d{6,9})"),
    ("Reactome", "bio", r"(R-[A-Z]{3}-\d+)"),
    ("Ensembl", "bio", r"\b(ENS[A-Z]*[GTP]\d{11})"),
    ("UniProt", "bio", r"(?i:uniprot)[a-z]*[/:]([A-Z0-9]{6,10})\b"),
    ("InChIKey", "bio", r"\b([A-Z]{14}-[A-Z]{10}-[A-Z])\b"),
    ("CAS", "bio", r"(?:^|/|:)(\d{2,7}-\d{2}-\d)$"),
    ("DrugBank", "bio", r"\b(DB\d{5})\b"),
    ("ChEMBL", "bio", r"\b(CHEMBL\d+)\b"),
    ("PubChem_CID", "bio", r"(?:compound/|CID|cid[/:_]?|pubchem\.compound[/:])(\d+)\b"),
    ("Entrez", "bio", r"(?:ncbigene|NCBIGene|ncbi\.nlm\.nih\.gov/gene|entrez)[/:_](\d+)\b"),
    ("HGNC", "bio", r"(?i:hgnc)[:_/](\d+)\b"),
    ("SNOMEDCT", "bio", r"SNOMEDCT(?:_US)?[:_/](\d+)\b"),
    # rs numbers only in dbSNP contexts: DOIs such as 10.3390/rs17020314 (the journal
    # Remote Sensing) also contain "rs" followed by digits.
    ("dbSNP", "bio", r"(?i:ncbi\.nlm\.nih\.gov/snp/|dbsnp[:/_]|^)(rs\d+)$"),
    ("S2_L13", "geo", r"s2[._]?level[._]?13[._](\d+)"),
    # county and state FIPS appear as KnowWhereGraph regions, Data Commons geoIds and
    # SPOKE-OKN location IRIs (other graphs reuse the SPOKE-OKN ones).
    ("county_FIPS", "geo", r"(?:administrativeRegion[._]USA[._]|datacommons\.org/(?:browser/)?geoId/|kg/spoke-okn/location/)(\d{5})$"),
    ("state_FIPS", "geo", r"(?:administrativeRegion[._]USA[._]|datacommons\.org/(?:browser/)?geoId/|kg/spoke-okn/location/)(\d{2})$"),
]
_COMPILED = [(n, f, re.compile(p)) for n, f, p in _SCHEMES]
FAMILY = {n: f for n, f, _ in _SCHEMES}
FAMILY.update({"ZIP5": "geo", "NAICS": "other", "county_FIPS": "geo", "state_FIPS": "geo", "LABEL": "label"})

# Any other OBO term (NCIT, BTO, PATO, SO, ...) keeps its own prefix as the scheme.
_OBO = re.compile(r"purl\.obolibrary\.org/obo/([A-Za-z]+)_([A-Za-z0-9]+)$")

# Schemes whose values are bare numbers: recognised only when the catalog names them.
_DIGITS = re.compile(r"[\d\s-]+")
_HINTED_NUMERIC = {
    # ZIP codes stored as numbers lose leading zeros ("603" is 00603); ZIP+4 keeps the first five.
    "ZIP5": lambda v: (lambda d: d.zfill(5) if 3 <= len(d) <= 5 else (d[:5] if len(d) == 9 else None))(re.sub(r"[^0-9]", "", v)),
    # whole values only: taking the last digits of a longer number (a ZIP such as 22848)
    # would invent a county or state.
    "county_FIPS": lambda v: (m.group(1).zfill(5) if (m := re.fullmatch(r"\s*(\d{4,5})\s*", v)) else None),
    "state_FIPS": lambda v: (m.group(1).zfill(2) if (m := re.fullmatch(r"\s*(\d{1,2})\s*", v)) else None),
    "Entrez": lambda v: (m.group(1) if (m := re.search(r"(\d+)$", v)) else None),
    "PubChem_CID": lambda v: (m.group(1) if (m := re.search(r"(\d+)$", v)) else None),
    "NAICS": lambda v: (m.group(1) if (m := re.search(r"(\d{2,6})$", v)) else None),
    "S2_L13": lambda v: (m.group(1) if (m := re.search(r"(\d{6,})$", v)) else None),
    "dbSNP": lambda v: ("rs" + m.group(1) if (m := re.fullmatch(r"\s*(\d+)\s*", v)) else None),
}

# Bare codes without a scheme marker, accepted only when the catalog names the scheme.
_HINTED_BARE = {
    "UMLS": re.compile(r"(C\d{7})"),
    "MeSH": re.compile(r"([DC]\d{6,9})"),
    "dbSNP": re.compile(r"(rs\d+)"),
}

# Catalog `shared_key` text -> scheme names it mentions.
_HINT_WORDS = [
    ("ZIP", "ZIP5"), ("county_FIPS", "county_FIPS"), ("KWG_county", "county_FIPS"),
    ("state_FIPS", "state_FIPS"), ("S2", "S2_L13"), ("NAICS", "NAICS"),
    ("Entrez", "Entrez"), ("NCBIGene", "Entrez"), ("PubChem", "PubChem_CID"),
    ("MONDO", "MONDO"), ("DOID", "DOID"), ("HP", "HP"), ("UBERON", "UBERON"), ("CL", "CL"),
    ("CHEBI", "CHEBI"), ("NCBITaxon", "NCBITaxon"), ("GO", "GO"), ("EFO", "EFO"),
    ("OMIM", "OMIM"), ("Orphanet", "Orphanet"), ("UMLS", "UMLS"), ("MeSH", "MeSH"),
    ("Reactome", "Reactome"), ("Ensembl", "Ensembl"), ("UniProt", "UniProt"),
    ("InChIKey", "InChIKey"), ("CAS", "CAS"), ("DrugBank", "DrugBank"), ("ChEMBL", "ChEMBL"),
    ("HGNC", "HGNC"), ("dbSNP", "dbSNP"),
]


def hinted_schemes(shared_key: str | None) -> list[str]:
    out = []
    for word, scheme in _HINT_WORDS:
        if shared_key and re.search(rf"(?<![A-Za-z]){re.escape(word)}", shared_key) and scheme not in out:
            out.append(scheme)
    return out


def canonical(value: str, scheme: str, numeric_ok: bool = True) -> str | None:
    """The canonical key for `value` under `scheme`, or None if it is not one.

    `numeric_ok` allows a bare number to count as an id of a numeric scheme (ZIP, FIPS,
    Entrez...). It is only safe when the catalog says which scheme to expect."""
    v = value.strip()
    for n, _, rx in _COMPILED:
        if n == scheme:
            m = rx.search(v)
            if m:
                return f"{scheme}:{m.group(1)}"
            break
    if numeric_ok and scheme in _HINTED_NUMERIC and _DIGITS.fullmatch(v):
        try:
            local = _HINTED_NUMERIC[scheme](v)
        except Exception:  # noqa: BLE001
            local = None
        return f"{scheme}:{local}" if local else None
    return None


def detect(samples: list[str], hints: list[str]) -> tuple[str | None, float]:
    """Pick the scheme most sample values belong to; bare numbers only for hinted schemes."""
    if not samples:
        return (hints[0] if hints else None), 0.0
    candidates = list(dict.fromkeys(hints + [n for n, _, _ in _SCHEMES]))
    best, rate = None, 0.0
    for scheme in candidates:
        ok = scheme in hints
        hit = sum(1 for s in samples if canonical(s, scheme, numeric_ok=ok)) / len(samples)
        if hit > rate or (hit == rate and hit > 0 and ok and best not in hints):
            best, rate = scheme, hit
    return best, rate


def canon_any(value: str, hints: list[str]) -> str | None:
    """Canonical key under whichever scheme the value belongs to.

    Recognisable identifiers (IRIs/CURIEs with a scheme marker) win; a bare number is
    only accepted for a numeric scheme the catalog named for this endpoint."""
    v = value.strip()
    for n, _, rx in _COMPILED:
        m = rx.search(v)
        if m:
            return f"{n}:{m.group(1)}"
    m = _OBO.search(v)
    if m:
        return f"{m.group(1).upper()}:{m.group(2)}"
    if _DIGITS.fullmatch(v):
        for h in hints:
            if h in _HINTED_NUMERIC:
                k = canonical(v, h, numeric_ok=True)
                if k:
                    return k
    for h in hints:
        rx = _HINTED_BARE.get(h)
        if rx and (m := rx.fullmatch(v)):
            return f"{h}:{m.group(1)}"
    return None


def label_key(value: str) -> str | None:
    """Fallback key for label joins (county names, industry sectors, species names).

    Used only for endpoints whose values are mostly plain strings with no recognisable
    identifier; reported separately because a shared name is weaker evidence than a
    shared identifier."""
    v = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip().casefold()
    if not v or len(v) < 2 or _DIGITS.fullmatch(v) or v.startswith(("http://", "https://")):
        return None
    return f"LABEL:{v}"


# Standard IRI namespaces per scheme. Used to narrow "membership-only" patterns (?k0 is a
# subject of some triple) to the terms that can be join keys at all.
NAMESPACES = {
    "MONDO": ["http://purl.obolibrary.org/obo/MONDO_"],
    "DOID": ["http://purl.obolibrary.org/obo/DOID_"],
    "HP": ["http://purl.obolibrary.org/obo/HP_"],
    "UBERON": ["http://purl.obolibrary.org/obo/UBERON_"],
    "CL": ["http://purl.obolibrary.org/obo/CL_"],
    "GO": ["http://purl.obolibrary.org/obo/GO_"],
    "CHEBI": ["http://purl.obolibrary.org/obo/CHEBI_"],
    "NCBITaxon": ["http://purl.obolibrary.org/obo/NCBITaxon_"],
    "EFO": ["http://www.ebi.ac.uk/efo/EFO_"],
    "Entrez": ["http://identifiers.org/ncbigene/", "https://identifiers.org/ncbigene/", "http://www.ncbi.nlm.nih.gov/gene/"],
    "Ensembl": ["http://identifiers.org/ensembl/", "https://identifiers.org/ensembl/"],
    "UniProt": ["http://purl.uniprot.org/uniprot/", "https://identifiers.org/uniprot/", "http://identifiers.org/uniprot/"],
    "MeSH": ["http://id.nlm.nih.gov/mesh/"],
    "HGNC": ["http://identifiers.org/hgnc/", "https://identifiers.org/hgnc/"],
    "CAS": ["http://identifiers.org/cas/", "https://identifiers.org/cas/"],
}
_VOCAB = ("https://schema.org/", "http://schema.org/", "http://www.w3.org/", "http://xmlns.com/",
          "http://purl.org/dc/", "https://w3id.org/")


def key_namespaces(hints, quoted):
    """Namespaces a membership-only pattern's keys can start with: the ones the catalog's
    query quotes, plus the standard ones of its hinted schemes, minus vocabularies."""
    out = [ns for ns in quoted if not ns.startswith(_VOCAB)]
    for h in hints:
        out += NAMESPACES.get(h, [])
    return list(dict.fromkeys(out))
