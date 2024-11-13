# -*- coding: utf-8 -*-
"""Main entry point for Pype command."""
from . import cli
import sys
import traceback

if __name__ == '__main__':
    try:
        cli.main(obj={}, prog_name="quadpype")
    except Exception:
        exc_info = sys.exc_info()
        print("!!! QuadPype crashed:")
        traceback.print_exception(*exc_info)
        sys.exit(1)
