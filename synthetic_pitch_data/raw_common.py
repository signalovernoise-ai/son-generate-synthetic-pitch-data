from __future__ import annotations

from pathlib import Path

import pandas as pd

from synthetic_pitch_data.paths import SOURCE_ROOT


def write_source_csv(df: pd.DataFrame, folder: str, filename: str) -> Path:
    output_dir = SOURCE_ROOT / folder
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    df.to_csv(output_path, index=False)
    return output_path


def print_source_summary(label: str, rows: int, output_path: Path) -> None:
    print(f"{label}: wrote {rows:,} rows to {output_path}")
