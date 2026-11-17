# 10 · Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `'ocm' is not recognized` / `command not found` | The environment is not active | Run `.venv\Scripts\activate` (Windows), `source .venv/bin/activate` (macOS/Linux) or `conda activate okn`, or use `python -m okn_connection_map` instead of `ocm` |
| `ocm check`: FAIL on SPARQL or KGF with `Tunnel connection failed`, `403`, `timed out`, or `getaddrinfo failed` | A firewall, proxy or VPN blocks `apps.okn.us` | Try another network, or turn the VPN off or on. On a university network, ask IT to allow `apps.okn.us` (HTTPS). Offline commands still work |
| `ocm fetch-catalog` fails | GitHub is blocked | Download `crosswalks.json` in a browser from the address in [03](03_getting_the_data.md), then set `OCM_CATALOG` to its path |
| `No crosswalk catalog at ...` | The catalog has not been downloaded | `ocm fetch-catalog` |
| `No computed run under ...` | No run yet in this working folder | `ocm use-sample`, or `ocm all --label <name>`. Check you are in the same folder, or that `OCM_HOME` is set the same way |
| A query fails with `timed out after 120s` | The federation is busy, or the pattern is large | Run the same command again (runs resume); raise `--timeout`; run at a quieter time |
| `too_large` for some patterns | The identifier set is above `--cap` | Expected. Those pairs say "not measured". Raise `--cap` only if you have time and disk space |
| `PowerShell: running scripts is disabled` when activating | PowerShell policy | Use Command Prompt, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| Claude Desktop does not show the tools | Wrong path to `ocm`, or `OCM_HOME` not set | Use the full path from `where ocm` / `which ocm`. Set `OCM_HOME` in the config's `env`. Restart Claude Desktop and check its MCP log (Settings → Developer) |
| Strange characters in Windows output | Console code page | Run `chcp 65001` once in the window |
| Numbers differ from the README | The graphs or the catalog have changed since October 2026 | Expected. `ocm followup` and `ocm diff` show what changed |

Still stuck? Open an issue and include the output of `ocm check`. Remove anything private first.
