#!/usr/bin/env python3
"""Simple web server entry point."""

import argparse
import os
import sys

# Add the module to path
sys.path.insert(0, os.path.dirname(__file__))

from test_report_viewer.adapters.web.app import create_app
from test_report_viewer.config import load_config

def parse_args():
    parser = argparse.ArgumentParser(description="Test Report Viewer Web Server")
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Path to config file")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")),
                        help="Port to run on")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Host to bind to")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # Load config
    config = load_config(args.config)

    # Create and run app
    app = create_app(config)
    print(f"Starting web server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)