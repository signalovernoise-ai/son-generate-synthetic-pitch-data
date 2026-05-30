from __future__ import annotations

from pathlib import Path

import pandas as pd

from synthetic_pitch_data.paths import SOURCE_ROOT, STAGE_ROOT


TEST_REGEX = r"(?:test|qa\+|dev|staff|staging|@example|\.internal|@.*\.test)"

COUNTRY_MAP = {
    "gb": "GB",
    "uk": "GB",
    "united kingdom": "GB",
    "england": "GB",
}


def to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def format_utc(series: pd.Series) -> pd.Series:
    formatted = series.dt.strftime("%Y-%m-%dT%H:%M:%SZ").astype("string")
    return formatted.where(series.notna(), pd.NA)


def normalize_country(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    cleaned = cleaned.where(cleaned.ne(""), pd.NA)
    mapped = cleaned.str.lower().map(COUNTRY_MAP).astype("string")
    return mapped.fillna(cleaned)


def clean_string(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    return cleaned.where(cleaned.ne(""), pd.NA)


def test_pattern_mask(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing = [col for col in columns if col in df.columns]
    if not existing:
        return pd.Series(False, index=df.index)
    text = df[existing].fillna("").astype(str).agg(" ".join, axis=1)
    return text.str.contains(TEST_REGEX, case=False, regex=True, na=False)


def write_stage_csv(df: pd.DataFrame, folder: str, filename: str) -> Path:
    output_dir = STAGE_ROOT / folder
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    df.to_csv(output_path, index=False)
    return output_path


def print_summary(label: str, raw_rows: int, output_rows: int, output_path: Path) -> None:
    print(f"{label}: {raw_rows:,} source rows -> {output_rows:,} staged rows")
    print(f"Wrote {output_path}")
