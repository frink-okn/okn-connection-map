"""Lets `python -m okn_connection_map ...` work exactly like the `ocm` command."""
import sys

from .cli import main

sys.exit(main())
