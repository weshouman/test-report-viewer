"""Simple configuration management."""

import os
import yaml

DEFAULT_CONFIG = {
    "projects": [],
    "summary_runs": 10,
    "scan_interval": 10,
    "default_project_id": None,
    "default_project_identifier": None,
}

def load_config(config_path: str = None, overrides: dict = None) -> dict:
    """Load configuration from file and apply overrides."""
    config = DEFAULT_CONFIG.copy()

    # Load from file if provided and exists
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            file_config = yaml.safe_load(f) or {}
            config.update(file_config)

    # Apply overrides
    if overrides:
        config.update(overrides)

    return config