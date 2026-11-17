"""XXH64 seed 0, the hash KGF uses for its key sets (hdtc iri_hash, convention 1). Usage: python kgf_hash.py <IRI> ..."""
import struct, sys
M = (1 << 64) - 1
P1, P2, P3, P4, P5 = 11400714785074694791, 14029467366897019727, 1609587929392839161, 9650029242287828579, 2870177450012600261
rotl = lambda x, r: ((x << r) | (x >> (64 - r))) & M
def rnd(acc, lane): return (rotl((acc + lane * P2) & M, 31) * P1) & M
def merge(acc, v): return ((acc ^ rnd(0, v)) * P1 + P4) & M
def xxh64(b: bytes, seed=0) -> int:
    n, i = len(b), 0
    if n >= 32:
        v = [(seed + P1 + P2) & M, (seed + P2) & M, seed, (seed - P1) & M]
        while i + 32 <= n:
            for j in range(4):
                v[j] = rnd(v[j], struct.unpack_from('<Q', b, i + 8 * j)[0])
            i += 32
        h = (rotl(v[0], 1) + rotl(v[1], 7) + rotl(v[2], 12) + rotl(v[3], 18)) & M
        for x in v: h = merge(h, x)
    else:
        h = (seed + P5) & M
    h = (h + n) & M
    while i + 8 <= n:
        h = (rotl(h ^ rnd(0, struct.unpack_from('<Q', b, i)[0]), 27) * P1 + P4) & M; i += 8
    if i + 4 <= n:
        h = (rotl(h ^ (struct.unpack_from('<I', b, i)[0] * P1 & M), 23) * P2 + P3) & M; i += 4
    while i < n:
        h = (rotl(h ^ (b[i] * P5 & M), 11) * P1) & M; i += 1
    h ^= h >> 33; h = h * P2 & M; h ^= h >> 29; h = h * P3 & M; h ^= h >> 32
    return h
if __name__ == '__main__':
    for s in sys.argv[1:] or ['']:
        print(f'0x{xxh64(s.encode("utf-8")):016X}  {s!r}')
