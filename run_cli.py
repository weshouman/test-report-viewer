#!/usr/bin/env python3
"""Simple CLI entry point."""

import os
import sys

# Add the module to path
sys.path.insert(0, os.path.dirname(__file__))

from test_report_viewer.adapters.cli.commands import cli

if __name__ == "__main__":
    cli()