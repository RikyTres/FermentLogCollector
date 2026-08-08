from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.environ.get("FERMENT_COLLECTOR_DATA_DIR", "data")).resolve()


def database_path() -> Path:
    return data_dir() / "fermentlogcollector.sqlite3"
