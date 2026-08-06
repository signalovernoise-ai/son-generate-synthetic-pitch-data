"""Shared cleaning primitives: helpers, the dataset spec, the detector battery,
and the cleaning-notes renderer.

Design rules:
- Detectors are generic and schema-aware, never company-aware. They *measure*
  what is in the data and report counts; they never assume a known prevalence.
- Knowing a column's name/role is allowed (that is real schema knowledge a data
  team has). Knowing what quirks were injected is not — discover those.
- Normalizers fix in place and report how many values changed. Filters return a
  drop mask (True = drop) and report how many rows would be removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

TEST_REGEX = r"(?:\btest\b|qa\+|\bdev\b|staff|staging|@example|\.internal|@.*\.test)"

COUNTRY_MAP = {
    "gb": "GB",
    "uk": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "us": "US",
    "usa": "US",
    "united states": "US",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def format_utc(series: pd.Series) -> pd.Series:
    formatted = series.dt.strftime("%Y-%m-%dT%H:%M:%SZ").astype("string")
    return formatted.where(series.notna(), pd.NA)


def clean_string(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    return cleaned.where(cleaned.ne(""), pd.NA)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    detector: str
    found: int
    action: str  # removed | normalized | flagged | derived | none
    detail: str = ""


@dataclass
class StageReport:
    dataset: str
    source_file: str
    input_rows: int
    output_rows: int = 0
    findings: list[Finding] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def record(self, detector: str, found: int, action: str, detail: str = "") -> None:
        self.findings.append(Finding(detector, found, action, detail))

    def note(self, text: str) -> None:
        self.assumptions.append(text)


# ---------------------------------------------------------------------------
# Dataset spec
# ---------------------------------------------------------------------------
@dataclass
class DatasetSpec:
    name: str                                   # canonical output filename
    role: str                                   # logical role (orders, customers, ...)
    source_files: list[str]                     # candidate raw filenames; first present wins
    key: str | None = None                      # primary key (deduped, kept-first)
    display_id_col: str | None = None           # human display id (duplicate-looking but valid)
    required: list[str] = field(default_factory=list)
    timestamp_cols: list[str] = field(default_factory=list)
    reversal_pairs: list[tuple[str, str]] = field(default_factory=list)  # (earlier, later)
    primary_timestamp: str | None = None
    amount_col: str | None = None
    amount_bounds: tuple[float, float] | None = None
    email_cols: list[str] = field(default_factory=list)
    country_cols: list[str] = field(default_factory=list)
    upper_cols: list[str] = field(default_factory=list)        # normalize to UPPER (currency)
    lower_enum_cols: list[str] = field(default_factory=list)   # normalize to lower (status/type)
    test_pattern_cols: list[str] = field(default_factory=list)
    status_col: str | None = None
    keep_statuses: set[str] | None = None
    near_dup_group: list[str] = field(default_factory=list)
    fks: list[tuple[str, str, str]] = field(default_factory=list)  # (col, parent_role, parent_key)
    provides_keys: list[str] = field(default_factory=list)         # cols children may FK to (parent side)
    field_map: dict[str, str] = field(default_factory=dict)        # source -> canonical
    output_cols: list[str] | None = None                           # None = keep all (cleaned)
    pre_hooks: list[Callable] = field(default_factory=list)        # (df, report) -> df
    post_hooks: list[Callable] = field(default_factory=list)       # (df, report) -> df
    static_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalizers (fix in place, report count changed)
# ---------------------------------------------------------------------------
def normalize_emails(df: pd.DataFrame, cols: list[str], report: StageReport) -> None:
    for col in cols:
        if col not in df.columns:
            continue
        original = df[col].astype("string")
        fixed = original.str.strip().str.lower()
        changed = int((original.fillna("") != fixed.fillna("")).sum())
        df[col] = fixed
        if changed:
            report.record("email_casing_whitespace", changed, "normalized", f"{col}: {changed} values lower/trimmed")


def normalize_countries(df: pd.DataFrame, cols: list[str], report: StageReport) -> None:
    for col in cols:
        if col not in df.columns:
            continue
        original = clean_string(df[col])
        mapped = original.str.lower().map(COUNTRY_MAP).astype("string")
        fixed = mapped.fillna(original)
        changed_mask = original.fillna("") != fixed.fillna("")
        changed = int(changed_mask.sum())
        df[col] = fixed
        if changed:
            pairs = pd.DataFrame({"a": original[changed_mask], "b": fixed[changed_mask]}).value_counts()
            sample = "; ".join(f"{a}→{b} ×{c:,}" for (a, b), c in pairs.head(4).items())
            report.record("country_normalization", changed, "normalized", f"{col}: {sample}")


def normalize_case(df: pd.DataFrame, cols: list[str], to: str, report: StageReport) -> None:
    """Collapse genuine casing/whitespace drift only.

    A value is "drift" only when the same normalized token appears under more than one
    raw spelling (e.g. 'Sent' and 'sent'). Columns that are merely consistently
    Title-cased are left untouched, so the notes don't report a blanket re-casing as
    if it were a defect.
    """
    for col in cols:
        if col not in df.columns:
            continue
        raw = df[col].astype("string")
        norm = raw.str.strip()
        norm = norm.str.upper() if to == "upper" else norm.str.lower()
        pair = pd.DataFrame({"raw": raw, "norm": norm}).dropna()
        variants = pair.groupby("norm")["raw"].nunique()
        drift_norms = set(variants[variants > 1].index)
        if not drift_norms:
            continue
        in_drift = norm.isin(drift_norms)
        changed = int((in_drift & (raw != norm)).sum())
        df.loc[in_drift, col] = norm[in_drift]
        if changed:
            report.record(
                "enum_casing_drift", changed, "normalized",
                f"{col}: {changed} rows collapsed across {len(drift_norms)} value(s) with mixed casing",
            )


# ---------------------------------------------------------------------------
# Filters (return drop mask True=drop, report count)
# ---------------------------------------------------------------------------
def _false(df: pd.DataFrame) -> pd.Series:
    return pd.Series(False, index=df.index)


def missing_required(df: pd.DataFrame, cols: list[str], report: StageReport) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return _false(df)
    drop = _false(df)
    for col in cols:
        drop = drop | clean_string(df[col]).isna()
    n = int(drop.sum())
    if n:
        report.record("missing_required_fields", n, "removed", f"required {cols}")
    return drop


def test_pattern_rows(df: pd.DataFrame, cols: list[str], report: StageReport) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return _false(df)
    text = df[cols].fillna("").astype(str).agg(" ".join, axis=1)
    drop = text.str.contains(TEST_REGEX, case=False, regex=True, na=False)
    n = int(drop.sum())
    if n:
        report.record("test_internal_rows", n, "removed", f"matched test/internal/staging in {cols}")
    return drop


def implausible_amount(df, col, bounds, report) -> pd.Series:
    if not col or col not in df.columns or not bounds:
        return _false(df)
    lo, hi = bounds
    amt = pd.to_numeric(df[col], errors="coerce")
    drop = amt.notna() & ((amt <= lo) | (amt >= hi))
    n = int(drop.sum())
    if n:
        report.record("implausible_amount", n, "removed", f"{col} outside ({lo}, {hi})")
    return drop


def timestamp_reversals(df, pairs, report) -> pd.Series:
    drop = _false(df)
    for earlier, later in pairs:
        if earlier not in df.columns or later not in df.columns:
            continue
        e, l = to_utc(df[earlier]), to_utc(df[later])
        bad = e.notna() & l.notna() & (l < e)
        if int(bad.sum()):
            report.record("timestamp_reversal", int(bad.sum()), "removed", f"{later} < {earlier}")
        drop = drop | bad
    return drop


def near_duplicates(df, group_cols, amount_col, ts_col, report, window_s=60) -> pd.Series:
    group_cols = [c for c in group_cols if c in df.columns]
    if not group_cols or not ts_col or ts_col not in df.columns:
        return _false(df)
    work = pd.DataFrame(index=df.index)
    work["_ts"] = to_utc(df[ts_col])
    keys = list(group_cols)
    if amount_col and amount_col in df.columns:
        work["_amt"] = pd.to_numeric(df[amount_col], errors="coerce").round(2)
        keys.append("_amt")
    for c in group_cols:
        work[c] = df[c]
    work = work.sort_values(keys + ["_ts"])
    gap = work.groupby(keys)["_ts"].diff().dt.total_seconds()
    dup_idx = work[gap.between(0, window_s, inclusive="both")].index
    drop = df.index.to_series().isin(dup_idx)
    n = int(drop.sum())
    if n:
        report.record("near_duplicate_rows", n, "removed", f"same {keys} within {window_s}s")
    return drop


def orphan_fks(df, fks, parents: dict[str, dict[str, set]], report) -> pd.Series:
    """parents maps parent_role -> {referenceable_column: set_of_values}."""
    drop = _false(df)
    for col, parent_role, parent_key in fks:
        if col not in df.columns:
            continue
        keyset = parents.get(parent_role, {}).get(parent_key)
        if keyset is None:
            continue  # parent not staged in this run -> can't check, skip
        vals = df[col]
        bad = vals.notna() & (vals != "") & (~vals.isin(keyset))
        n = int(bad.sum())
        if n:
            report.record("orphan_foreign_key", n, "removed", f"{col} -> {parent_role}.{parent_key} not found")
        drop = drop | bad
    return drop


def non_final_status(df, col, keep, report) -> pd.Series:
    if not col or col not in df.columns or not keep:
        return _false(df)
    status = df[col].astype("string").str.strip().str.lower()
    drop = status.notna() & (~status.isin({s.lower() for s in keep}))
    n = int(drop.sum())
    if n:
        kept = sorted(set(status[~drop].dropna().unique()))
        report.record("non_final_status", n, "removed", f"{col} not in {sorted(keep)}; kept {kept}")
    return drop


def duplicate_key(df, key, report) -> pd.Series:
    if not key or key not in df.columns:
        return _false(df)
    drop = df.duplicated(subset=[key], keep="first") & df[key].notna()
    n = int(drop.sum())
    if n:
        report.record("duplicate_primary_key", n, "removed", f"{key} duplicates (kept first)")
    return drop


def flag_duplicate_display_id(df, col, report) -> None:
    """Duplicate-looking display ids whose underlying key is unique are valid; flag, keep."""
    if not col or col not in df.columns:
        return
    dupes = int(df.duplicated(subset=[col], keep=False).sum())
    if dupes:
        report.record("duplicate_display_id", dupes, "flagged", f"{col}: {dupes} rows share a display id (kept; row key is unique)")


# ---------------------------------------------------------------------------
# Notes renderer
# ---------------------------------------------------------------------------
ACTION_VERB = {
    "removed": "Removed",
    "normalized": "Normalized",
    "flagged": "Flagged (retained)",
    "derived": "Derived",
    "none": "Observed",
}


def render_cleaning_notes(company: str, reports: list[StageReport], extra_sections: list[str] | None = None) -> str:
    lines = [f"# {company} — Stage Cleaning Notes", ""]
    lines.append(
        "Auto-generated by the staging detector battery. Issues were discovered from the "
        "data (profiling), not from any knowledge of how it was produced."
    )
    lines.append("")
    for r in reports:
        # Count rows actually dropped, not the sum of detector hits: a row can trip more
        # than one filter (a £0 test order is both test_internal_rows and
        # implausible_amount), and summing findings overstates the removal.
        removed = r.input_rows - r.output_rows
        flagged = sum(f.found for f in r.findings if f.action == "removed")
        overlap = "" if flagged == removed else f"; {flagged:,} detector hits across overlapping filters"
        lines.append(f"## {r.dataset}")
        lines.append("")
        lines.append(f"Source: `{r.source_file}`  ")
        lines.append(f"Rows: {r.input_rows:,} in → {r.output_rows:,} staged "
                     f"({removed:,} removed{overlap}).")
        lines.append("")
        if r.findings:
            lines.append("Detected and handled:")
            for f in r.findings:
                verb = ACTION_VERB.get(f.action, f.action)
                lines.append(f"- {verb}: **{f.detector}** — {f.found:,} — {f.detail}")
        else:
            lines.append("No issues detected by the battery; only schema standardization applied.")
        if r.assumptions:
            lines.append("")
            lines.append("Assumptions / limitations:")
            for a in r.assumptions:
                lines.append(f"- {a}")
        lines.append("")
    if extra_sections:
        for section in extra_sections:
            lines.append(section)
            lines.append("")
    return "\n".join(lines)
