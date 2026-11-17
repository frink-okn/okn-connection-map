# 02 · Installation

The tool needs only **Python 3.9 or newer**. It uses no third-party packages, so installation is quick and does not interfere with other software.

Choose **one** of the three routes below. Each ends with the same check.

---

## Route 1: Windows with Anaconda (recommended if you already use Anaconda)

1. Open **Anaconda Prompt** from the Start menu.
2. Go to the folder where you keep projects, for example:
   ```bat
   cd %USERPROFILE%\Documents
   ```
3. Get the code. With Git:
   ```bat
   git clone https://github.com/frink-okn/okn-connection-map.git
   ```
   Without Git: on the repository's GitHub page, click the green **Code** button, then **Download ZIP**, unzip it into this folder, and rename the folder to `okn-connection-map`.
4. Create a separate environment and install:
   ```bat
   cd okn-connection-map
   conda create -n okn python=3.11 -y
   conda activate okn
   pip install -e .
   ```
5. Next time, open Anaconda Prompt and run `conda activate okn`, then `cd` into the folder.

## Route 2: Windows with Python from python.org

1. Install Python from <https://www.python.org/downloads/>. On the first installer screen, tick **"Add python.exe to PATH"**.
2. Open **Command Prompt** (search for `cmd`).
3. Get the code (as in Route 1, step 3), then:
   ```bat
   cd okn-connection-map
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```
   Your prompt now starts with `(.venv)`. Next time, run `.venv\Scripts\activate` again from this folder.

   If PowerShell refuses to run `activate`, use Command Prompt instead, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Route 3: macOS or Linux

1. Check that you have Python 3.9 or newer: `python3 --version`. On macOS, if Python is missing, install it from python.org or run `xcode-select --install`.
2. Open **Terminal**, then:
   ```bash
   git clone https://github.com/frink-okn/okn-connection-map.git
   cd okn-connection-map
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

---

## Check the installation

```bash
ocm --version
ocm check
```

`ocm check` prints one line per test:

```
okn-connection-map 0.2.0   (Python 3.11.9)
  [PASS] Python 3.9 or newer                ...
  [PASS] working folder is writable         ...\okn-connection-map\ocm-data
  [SKIP] crosswalk catalog present          not yet - run: ocm fetch-catalog
  [PASS] FRINK SPARQL endpoint              https://apps.okn.us/federation/sparql  (... graphs report a version, 850 ms)
  [PASS] FRINK KGF service                  https://apps.okn.us/kgf  (... datasets)
  [SKIP] computed runs available            none yet - ... ocm use-sample
```

SKIP lines are steps you have not done yet. They are fine. For any FAIL, see [10 Troubleshooting](10_troubleshooting.md).

If `ocm` is "not recognized", the environment is not active (run the `activate` or `conda activate okn` line again), or use `python -m okn_connection_map` instead of `ocm` everywhere.

## Where files go

Everything the tool downloads or produces goes into one folder, **`ocm-data`**, inside the folder you run it from:

```
ocm-data/
├── catalog/crosswalks.json      MCP-OKN's crosswalk catalog (ocm fetch-catalog)
└── runs/<label>/                one folder per computed run (ocm all --label <label>)
```

To keep the data somewhere else, for example a larger disk, set `OCM_HOME` or pass `--home`:

```bat
set OCM_HOME=D:\okn-data                 (Windows, this window only)
```
```bash
export OCM_HOME=/data/okn                (macOS / Linux, this window only)
ocm --home /data/okn paths nde rdkg      (any system, one command)
```

All settings are listed in [`src/okn_connection_map/config.py`](../src/okn_connection_map/config.py).

## Run the tests (optional)

```bash
python -m unittest discover -s tests -v
```

The tests run offline in under a second.

## Uninstall

Delete the `okn-connection-map` folder. If you used Anaconda, also run `conda env remove -n okn`. Nothing is installed anywhere else.
