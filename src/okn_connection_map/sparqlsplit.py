import re
VAR = re.compile(r'\?([A-Za-z_][A-Za-z0-9_]*)')
GRAPH_IRI = re.compile(r'GRAPH\s*<https://purl\.org/okn/frink/kg/([^>]+)>', re.I)

def match_brace(s, i, open_='{', close='}'):
    depth = 0; j = i; inq = None
    while j < len(s):
        c = s[j]
        if inq:
            if c == '\\': j += 2; continue
            if c == inq: inq = None
        elif c in '"\'': inq = c
        elif c == '<':  # IRI
            k = s.find('>', j)
            if k != -1 and ' ' not in s[j:k] and '\n' not in s[j:k]: j = k + 1; continue
        elif c == open_: depth += 1
        elif c == close:
            depth -= 1
            if depth == 0: return j
        j += 1
    raise ValueError('unbalanced')

def where_body(q):
    m = re.search(r'\bWHERE\s*\{', q, re.I)
    if not m: return None
    start = m.end() - 1
    end = match_brace(q, start)
    return q[start + 1:end]

def top_items(body):
    """Split a group body into top-level items: ('graph', name, text), ('sub', text), ('bind'|'filter', text), ('union'/'other', text)."""
    items = []; i = 0; n = len(body)
    while i < n:
        c = body[i]
        if c.isspace() or c == '.': i += 1; continue
        m = re.match(r'GRAPH\s*<([^>]+)>\s*', body[i:], re.I)
        if m:
            j = i + m.end(); k = match_brace(body, j)
            g = GRAPH_IRI.match(body[i:])
            items.append(('graph', g.group(1) if g else m.group(1), body[i:k + 1])); i = k + 1; continue
        if c == '{':
            k = match_brace(body, i); txt = body[i:k + 1]
            rest = body[k + 1:].lstrip()
            if rest.upper().startswith('UNION'):
                # swallow whole union chain
                j = k + 1
                while True:
                    r = body[j:].lstrip(); off = len(body[j:]) - len(r)
                    if r.upper().startswith('UNION'):
                        j2 = j + off + 5; r2 = body[j2:].lstrip(); off2 = len(body[j2:]) - len(r2)
                        kk = match_brace(body, j2 + off2); j = kk + 1
                    else: break
                items.append(('union', None, body[i:j])); i = j; continue
            if re.match(r'\{\s*SELECT\b', txt, re.I): items.append(('sub', None, txt))
            else: items.append(('group', None, txt))
            i = k + 1; continue
        m = re.match(r'(BIND|FILTER|VALUES|OPTIONAL|MINUS)\b', body[i:], re.I)
        if m:
            kw = m.group(1).upper(); j = i + m.end()
            while body[j].isspace(): j += 1
            if body[j] == '(':
                k = match_brace(body, j, '(', ')')
            elif body[j] == '{':
                k = match_brace(body, j)
            else:
                k = body.find('}', j) if kw == 'VALUES' else j
            items.append((kw.lower(), None, body[i:k + 1])); i = k + 1; continue
        # unknown token: consume to next whitespace
        j = i
        while j < n and not body[j].isspace(): j += 1
        items.append(('other', None, body[i:j])); i = j
    return items

def vars_of(t): return set(VAR.findall(t))
