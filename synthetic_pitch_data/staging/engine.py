"""Generic cleaning engine: run a DatasetSpec's battery over a raw frame.

The order of operations is fixed and deliberate: normalize values first (so
downstream comparisons see clean values), then drop rows via the filter battery,
then derive/standardize, then project to the canonical output columns.
"""

from __future__ import annotations

import pandas as pd

from .cleaning_common import (
    DatasetSpec,
    StageReport,
    duplicate_key,
    flag_duplicate_display_id,
    format_utc,
    implausible_amount,
    line_economics,
    missing_required,
    near_duplicates,
    non_final_status,
    normalize_case,
    normalize_countries,
    normalize_emails,
    orphan_fks,
    test_pattern_rows,
    timestamp_reversals,
    to_utc,
)


def run_dataset(
    spec: DatasetSpec,
    raw: pd.DataFrame,
    parents: dict[str, set],
    source_file: str,
) -> tuple[pd.DataFrame, StageReport]:
    df = raw.copy()
    report = StageReport(spec.name, source_file, len(df))

    # Schema standardization: rename source columns to canonical (adapters/drift).
    if spec.field_map:
        df = df.rename(columns={k: v for k, v in spec.field_map.items() if k in df.columns})

    for hook in spec.pre_hooks:
        df = hook(df, report)

    # --- normalize in place ---
    normalize_emails(df, spec.email_cols, report)
    normalize_countries(df, spec.country_cols, report)
    normalize_case(df, spec.upper_cols, "upper", report)
    normalize_case(df, spec.lower_enum_cols, "lower", report)
    flag_duplicate_display_id(df, spec.display_id_col, report)

    # --- row-drop battery ---
    drop = pd.Series(False, index=df.index)
    drop |= missing_required(df, spec.required, report)
    drop |= test_pattern_rows(df, spec.test_pattern_cols, report)
    drop |= implausible_amount(df, spec.amount_col, spec.amount_bounds, report)
    drop |= timestamp_reversals(df, spec.reversal_pairs, report)
    drop |= near_duplicates(df, spec.near_dup_group, spec.amount_col, spec.primary_timestamp, report)
    drop |= orphan_fks(df, spec.fks, parents, report)
    drop |= non_final_status(df, spec.status_col, spec.keep_statuses, report)
    drop |= duplicate_key(df, spec.key, report)

    clean = df[~drop].copy()

    # --- derive/flag on the surviving rows ---
    clean = line_economics(clean, spec, report)

    for hook in spec.post_hooks:
        clean = hook(clean, report)

    # Standardize timestamps to UTC ISO 8601.
    for col in spec.timestamp_cols:
        if col in clean.columns:
            clean[col] = format_utc(to_utc(clean[col]))

    if spec.output_cols:
        clean = clean[[c for c in spec.output_cols if c in clean.columns]]

    for note in spec.static_notes:
        report.note(note)
    report.output_rows = len(clean)
    return clean.reset_index(drop=True), report


def key_set(df: pd.DataFrame, key: str) -> set:
    if df is None or key not in df.columns:
        return set()
    return set(df[key].dropna().astype(str))
