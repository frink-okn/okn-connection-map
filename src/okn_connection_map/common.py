"""Shared plumbing: paths, the read-only SPARQL/KGF client, small file helpers.

Standard library only (Python 3.9+): nothing to install beyond Python itself.
The SPARQL client applies the same <https://schema.org/ -> <http://schema.org/
canonicalization MCP-OKN applies, retries only transient HTTP statuses, and never raises.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

from . import config
from . import __version__

GRAPH_PREFIX = "https://purl.org/okn/frink/kg/"
USER_AGENT = f"okn-connection-map/{__version__} (read-only research tool)"
TRANSIENT = {429, 502, 503, 504}
_SCHEMA_ORG = re.compile(r"<https://schema\.org/")


class Meter:
    """Counts what the run asked of the public services."""
    def __init__(self) -> None:
        self.requests = 0
        self.bytes = 0
        self.seconds = 0.0

    def add(self, nbytes: int, seconds: float) -> None:
        self.requests += 1
        self.bytes += nbytes
        self.seconds += seconds

    def as_dict(self) -> dict:
        return {"requests": self.requests, "bytes": self.bytes, "seconds": round(self.seconds, 1)}


METER = Meter()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(msg, flush=True)


def _post(url: str, body: bytes, accept: str, timeout: float, retries: int = 3) -> dict:
    rec: dict[str, Any] = {"ok": False, "status": None, "error_kind": None, "error": None,
                           "body": b"", "elapsed_ms": None, "attempts": 0}
    for attempt in range(1, retries + 2):
        rec["attempts"] = attempt
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Accept": accept, "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            el = time.perf_counter() - t0
            METER.add(len(raw), el)
            rec.update(ok=True, status=200, body=raw, elapsed_ms=round(el * 1000, 1))
            return rec
        except urllib.error.HTTPError as e:
            el = time.perf_counter() - t0
            METER.add(0, el)
            try:
                msg = e.read().decode("utf-8", "replace")[:600]
            except Exception:  # noqa: BLE001
                msg = str(e)
            rec.update(status=e.code, error=msg, elapsed_ms=round(el * 1000, 1))
            if e.code in TRANSIENT and attempt <= retries:
                time.sleep(min(30, 3 * attempt))
                continue
            rec["error_kind"] = "http_error"
            return rec
        except (socket.timeout, TimeoutError):
            METER.add(0, time.perf_counter() - t0)
            rec.update(error_kind="timeout", error=f"timed out after {timeout}s")
            return rec
        except urllib.error.URLError as e:
            METER.add(0, time.perf_counter() - t0)
            reason = getattr(e, "reason", e)
            if "timed out" in str(reason):
                rec.update(error_kind="timeout", error=f"timed out after {timeout}s")
                return rec
            rec.update(error_kind="network", error=str(reason))
            if attempt <= retries:
                time.sleep(min(30, 3 * attempt))
                continue
            return rec
    return rec


def sparql_rows(query: str, timeout: float = 120.0) -> dict:
    """Run a SELECT and return {'ok', 'columns', 'rows' (list of dicts of lexical values), ...}.

    Uses CSV results: IRIs and literals come back as their lexical values, which is all
    the canonicalizers need, and CSV is several times smaller than JSON for big key sets."""
    q = _SCHEMA_ORG.sub("<http://schema.org/", query)
    rec = _post(config.sparql_endpoint(), urllib.parse.urlencode({"query": q}).encode(), "text/csv", timeout)
    out = {k: rec[k] for k in ("ok", "status", "error_kind", "error", "elapsed_ms")}
    out.update(columns=[], rows=[], bytes=len(rec["body"]), query=q)
    if rec["ok"]:
        try:
            text = rec["body"].decode("utf-8")
            reader = csv.reader(io.StringIO(text))
            header = next(reader, [])
            out["columns"] = [h.lstrip("?") for h in header]
            out["rows"] = [dict(zip(out["columns"], r)) for r in reader]
        except Exception as e:  # noqa: BLE001
            out.update(ok=False, error_kind="bad_response", error=str(e)[:300])
    return out


def sparql_count(query: str, timeout: float = 120.0) -> tuple[int | None, dict]:
    r = sparql_rows(query, timeout)
    if not r["ok"] or not r["rows"]:
        return None, r
    try:
        return int(float(next(iter(r["rows"][0].values())))), r
    except (ValueError, StopIteration):
        return None, r


def get_json(url: str, timeout: float = 60.0) -> tuple[Any, dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        METER.add(len(raw), time.perf_counter() - t0)
        return json.loads(raw.decode("utf-8")), {"ok": True}
    except Exception as e:  # noqa: BLE001
        METER.add(0, time.perf_counter() - t0)
        return None, {"ok": False, "error": str(e)[:300]}


VERSION_QUERY = """SELECT ?s ?version ?last_updated WHERE {
  GRAPH <https://purl.org/okn/frink/kg/okn-void> {
    ?s <http://purl.org/pav/version> ?version .
    OPTIONAL { ?s <http://purl.org/pav/lastUpdatedOn> ?last_updated }
  }
}"""


def fetch_versions() -> dict:
    r = sparql_rows(VERSION_QUERY)
    out = {}
    for row in r.get("rows", []):
        out[row.get("s", "").replace(GRAPH_PREFIX, "", 1)] = {
            "version": row.get("version"), "last_updated": row.get("last_updated")}
    return out


def load_catalog(required: bool = True) -> dict:
    """The MCP-OKN crosswalk catalog (run `ocm fetch-catalog` once to download it)."""
    p = config.catalog_path()
    if not p.exists():
        if required:
            raise SystemExit(f"No crosswalk catalog at {p}.\nDownload it first:  ocm fetch-catalog")
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_keys(path: Path, keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(keys)))


def read_keys(path: Path) -> set[str]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return {line for line in fh.read().split("\n") if line}
