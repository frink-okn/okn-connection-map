"""Where the tool reads and writes, and which services it talks to.

Every setting has a default that works after a plain `git clone`, and can be changed
with an environment variable or a command-line option (`ocm --home PATH ...`).

  OCM_HOME             working folder for downloads and results   (default: ./ocm-data)
  OCM_CATALOG          MCP-OKN crosswalk catalog (crosswalks.json) (default: <home>/catalog/crosswalks.json)
  OCM_CATALOG_URL      where `ocm fetch-catalog` downloads it from (default: MCP-OKN on GitHub)
  OCM_SPARQL_ENDPOINT  FRINK federated SPARQL endpoint             (default: https://apps.okn.us/federation/sparql)
  OCM_KGF_ROOT         FRINK KGF service                           (default: https://apps.okn.us/kgf)
  OCM_AUDIT_DIR        optional: outputs of an earlier MCP-OKN audit (tool answers recorded per pair)
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_CATALOG_URL = "https://raw.githubusercontent.com/sbl-sdsc/mcp-okn/main/metadata/crosswalks.json"
DEFAULT_SPARQL_ENDPOINT = "https://apps.okn.us/federation/sparql"
DEFAULT_KGF_ROOT = "https://apps.okn.us/kgf"

_home_override: Path | None = None


def set_home(path: str | os.PathLike | None) -> None:
    """Use this folder for downloads and results (the CLI's --home)."""
    global _home_override
    _home_override = Path(path).expanduser().resolve() if path else None


def home() -> Path:
    if _home_override is not None:
        return _home_override
    return Path(os.environ.get("OCM_HOME") or (Path.cwd() / "ocm-data")).expanduser().resolve()


def runs_dir() -> Path:
    return home() / "runs"


def catalog_path() -> Path:
    env = os.environ.get("OCM_CATALOG")
    return Path(env).expanduser().resolve() if env else home() / "catalog" / "crosswalks.json"


def catalog_url() -> str:
    return os.environ.get("OCM_CATALOG_URL") or DEFAULT_CATALOG_URL


def sparql_endpoint() -> str:
    return os.environ.get("OCM_SPARQL_ENDPOINT") or DEFAULT_SPARQL_ENDPOINT


def kgf_root() -> str:
    return (os.environ.get("OCM_KGF_ROOT") or DEFAULT_KGF_ROOT).rstrip("/")


def audit_dir() -> Path | None:
    """Optional folder with an earlier audit's outputs (a1_pair_status.csv, b1_freshness_*.json)."""
    env = os.environ.get("OCM_AUDIT_DIR")
    p = Path(env).expanduser().resolve() if env else None
    return p if p and p.is_dir() else None
