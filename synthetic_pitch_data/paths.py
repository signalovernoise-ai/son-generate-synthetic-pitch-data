from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_HOME = REPO_ROOT.parent / "synthetic_data"
DATA_HOME = Path(os.getenv("SYNTHETIC_DATA_HOME", DEFAULT_DATA_HOME)).expanduser().resolve()

SOURCE_ROOT = DATA_HOME / "data" / "src"
STAGE_ROOT = DATA_HOME / "data" / "stage"
ANALYTICS_ROOT = DATA_HOME / "data" / "analytics"


def ensure_workspace_dirs() -> None:
    for path in [SOURCE_ROOT, STAGE_ROOT, ANALYTICS_ROOT]:
        path.mkdir(parents=True, exist_ok=True)
