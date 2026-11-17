import re, json, collections
from .sparqlsplit import where_body, top_items, vars_of, GRAPH_IRI
GENERIC = {'s','p','o','x','y','z','a','b','c','t','n'}
def graphs_in(text):
    return re.findall(r'GRAPH\s*<https://purl\.org/okn/frink/kg/([^>]+)>', text, re.I)
def counted_var(q):
    m = re.search(r'COUNT\s*\(\s*DISTINCT\s+\?(\w+)', q, re.I)
    return m.group(1) if m else None

def segments(q):
    items = top_items(where_body(q))
    segs = []
    for kind, name, text in items:
        if kind in ('graph', 'sub', 'group'):
            gs = graphs_in(text)
            if not gs: return None, 'segment without graph'
            if len(set(gs)) > 1: return None, 'segment spans several graphs'
            segs.append({'graph': gs[0], 'parts': [text]})
        elif kind in ('bind', 'filter'):
            if not segs:
                return None, 'leading bind/filter'
            segs[-1]['parts'].append(text)
        else:
            return None, f'unsupported item {kind}'
    for s in segs:
        s['text'] = '\n'.join(s['parts']); s['vars'] = vars_of(s['text'])
    return segs, None

def pick(shared, prefer):
    if prefer in shared: return prefer
    c = [v for v in shared if v not in GENERIC]
    if len(c) == 1: return c[0]
    if len(shared) == 1: return next(iter(shared))
    return None

def extract(entry):
    q = entry.get('skeleton_query')
    if not q: return None, 'no skeleton'
    try:
        segs, why = segments(q)
    except Exception as e:
        return None, f'parse error {e}'
    if segs is None: return None, why
    cv = counted_var(q)
    if len(segs) == 2:
        k = pick(segs[0]['vars'] & segs[1]['vars'], cv)
        if not k: return None, 'no single join variable'
        return {'kind': 'direct', 'ends': [(segs[0], k), (segs[1], k)], 'bridge': None}, None
    if len(segs) == 3:
        k0 = pick(segs[0]['vars'] & segs[1]['vars'], cv)
        k2 = pick(segs[1]['vars'] & segs[2]['vars'], cv)
        if not k0 or not k2: return None, 'no single join variable (3 segments)'
        if segs[0]['vars'] & segs[2]['vars'] - {k0, k2} - GENERIC:
            pass
        return {'kind': 'bridged', 'ends': [(segs[0], k0), (segs[2], k2)], 'bridge': (segs[1], k0, k2)}, None
    return None, f'{len(segs)} segments'


# ---------------------------------------------------------------------------
# Endpoints: the per-graph halves of the catalog's crosswalks
# ---------------------------------------------------------------------------
import hashlib
from .schemes import FAMILY, hinted_schemes

_VAR = re.compile(r'\?([A-Za-z_][A-Za-z0-9_]*)')


def rename_vars(text, keys):
    """Rename variables canonically: keys -> ?k0, ?k1..., others -> ?v1, ?v2... by first use.
    Two endpoints that differ only in variable names then have identical text."""
    mapping = {k: f"k{i}" for i, k in enumerate(keys)}
    n = 0
    def sub(m):
        nonlocal n
        v = m.group(1)
        if v not in mapping:
            n += 1
            mapping[v] = f"v{n}"
        return "?" + mapping[v]
    return _VAR.sub(sub, text)


def _norm_ws(t):
    return re.sub(r'\s+', ' ', t).strip()


_PREFIX = re.compile(r'PREFIX\s+[A-Za-z0-9_-]*:\s*<[^>]*>', re.I)
_NS_LIT = re.compile(r"""['"](https?://[^'"\s]+?[/#:_=])['"]""")
# A pattern that only says "?k0 is a subject (or object) of some triple in this graph":
# on its own it matches every term, so it must be narrowed to the key's namespace.
_MEMBERSHIP = re.compile(r'^GRAPH <[^>]+> \{ (?:\?k0 \?v\d+ \?v\d+|\?v\d+ \?v\d+ \?k0) \.? \}$')


def prefixes_of(q):
    """PREFIX declarations of a query, so extracted fragments stay valid SPARQL."""
    return '\n'.join(dict.fromkeys(_PREFIX.findall(q or '')))


def namespaces_of(q):
    """IRI namespaces quoted in a query (STRSTARTS/REPLACE/CONCAT arguments)."""
    return list(dict.fromkeys(_NS_LIT.findall(q or '')))


def build_endpoints(catalog):
    """Split every crosswalk the parser understands into endpoints and bridges.

    endpoint: one graph's pattern that binds ?k0 to the join key.
    bridge:   a connector graph's pattern that binds ?k0 (left key) and ?k1 (right key).
    """
    endpoints, bridges, crosswalks, skipped = {}, {}, [], []
    for e in catalog.get('verified_crosswalks', []):
        r, why = extract(e)
        if not r:
            skipped.append({'id': e['id'], 'reason': why})
            continue
        hints = hinted_schemes(e.get('shared_key'))
        refs = []
        for seg, key in r['ends']:
            frag = _norm_ws(rename_vars(seg['text'], [key]))
            eid = hashlib.sha1(f"{seg['graph']}|{frag}".encode()).hexdigest()[:10]
            ep = endpoints.setdefault(eid, {'id': eid, 'graph': seg['graph'], 'fragment': frag,
                                            'hints': [], 'crosswalks': [], 'prefixes': '',
                                            'membership_only': bool(_MEMBERSHIP.match(frag)),
                                            'namespaces': []})
            pre = prefixes_of(e.get('skeleton_query'))
            if pre:
                ep['prefixes'] = '\n'.join(dict.fromkeys((ep['prefixes'] + '\n' + pre).strip().split('\n')))
            for ns in namespaces_of(e.get('skeleton_query')):
                if ns not in ep['namespaces']:
                    ep['namespaces'].append(ns)
            for h in hints:
                if h not in ep['hints']:
                    ep['hints'].append(h)
            ep['crosswalks'].append(e['id'])
            refs.append(eid)
        bref = None
        if r['bridge']:
            seg, k0, k2 = r['bridge']
            frag = _norm_ws(rename_vars(seg['text'], [k0, k2]))
            bid = hashlib.sha1(f"{seg['graph']}|{frag}".encode()).hexdigest()[:10]
            b = bridges.setdefault(bid, {'id': bid, 'graph': seg['graph'], 'fragment': frag,
                                         'hints': hints, 'crosswalks': [],
                                         'prefixes': prefixes_of(e.get('skeleton_query'))})
            b['crosswalks'].append(e['id'])
            bref = bid
        crosswalks.append({'id': e['id'], 'kind': r['kind'], 'left': refs[0], 'right': refs[1],
                           'bridge': bref, 'left_kg': e.get('left_kg'), 'right_kg': e.get('right_kg'),
                           'bridge_kg': e.get('bridge_kg'), 'shared_key': e.get('shared_key'),
                           'verified_count': e.get('verified_count')})
    return list(endpoints.values()), list(bridges.values()), crosswalks, skipped


def in_scope(hints, families=('bio', 'geo')):
    """Keep endpoints whose catalog key is biomedical or geographic (or unknown: decided later)."""
    if not hints:
        return True
    return any(FAMILY.get(h) in families for h in hints)
