"""Stage and clean a company's raw extracts.

    python3 -m synthetic_pitch_data.staging.run_staging --company yumove

Detects which datasets the company produced, conforms non-Shopify commerce backends
to the Shopify shape, runs each dataset through the detector battery in dependency
order, writes cleaned stage tables, and emits a CLEANING_NOTES.md whose contents are
derived entirely from what the battery discovered in the data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ..paths import SOURCE_ROOT, STAGE_ROOT
from .adapters import custom_postgres
from .cleaning_common import render_cleaning_notes
from .engine import run_dataset
from .schema_registry import STAGE_SPECS


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _coverage_section(stage_dir: Path) -> str | None:
    """Cross-system observation: how completely downstream sources cover commerce orders.

    Window-aware: each downstream source is only expected to cover orders within its own
    observed date range, so a shorter implementation window is not mistaken for a gap.
    Discovered by joining staged tables — no knowledge of injected issues.
    """
    orders_path = stage_dir / "shopify_orders.csv"
    if not orders_path.exists():
        return None
    od = _read(orders_path)
    if od.empty:
        return None
    o_date = pd.to_datetime(od["created_at"], utc=True, errors="coerce").dt.date
    lines = ["## Cross-system coverage (observed)", "",
             f"Commerce orders staged: {len(od):,}.", ""]
    checks = [
        ("GA4 purchase events", "ga4_reporting_purchase_events.csv", "transactionId", "date"),
        ("Triple Whale attributed orders", "triple_whale_attributed_orders.csv", "order_id", "created_at"),
    ]
    found_any = False
    for label, fname, id_col, date_col in checks:
        p = stage_dir / fname
        if not p.exists():
            continue
        found_any = True
        src = _read(p)
        s_date = pd.to_datetime(src[date_col], utc=True, errors="coerce").dt.date.dropna()
        lo, hi = s_date.min(), s_date.max()
        in_win = od[(o_date >= lo) & (o_date <= hi)]
        denom = set(in_win["id"])
        covered = len(denom & set(src[id_col]))
        gap = len(denom) - covered
        pct = gap / len(denom) if denom else 0
        lines.append(
            f"- {label}: window {lo}…{hi}; {covered:,}/{len(denom):,} in-window orders present "
            f"({gap:,} = {pct:.1%} not attributed downstream)."
        )
    return "\n".join(lines) if found_any else None


def stage_company(slug: str) -> int:
    src = SOURCE_ROOT / slug
    if not src.exists():
        raise SystemExit(f"No raw data at {src}")
    stage_dir = STAGE_ROOT / slug
    stage_dir.mkdir(parents=True, exist_ok=True)

    # Conform a non-Shopify commerce backend to the Shopify shape up front.
    adapted: dict[str, pd.DataFrame] = {}
    if custom_postgres.detect(src):
        adapted = custom_postgres.adapt(src)
        print(f"commerce backend: custom Postgres → adapted {sorted(adapted)} to Shopify shape")
    else:
        print("commerce backend: Shopify (no adapter needed)")

    parents: dict[str, dict[str, set]] = {}
    reports = []

    for spec in STAGE_SPECS:
        # Resolve the source frame: adapter output first, then a present raw file.
        raw = None
        source_file = None
        if spec.name in adapted:
            raw, source_file = adapted[spec.name], f"adapter:custom_postgres → {spec.name}"
        else:
            for candidate in spec.source_files:
                if (src / candidate).exists():
                    raw, source_file = _read(src / candidate), candidate
                    break
        if raw is None:
            continue  # company did not produce this dataset

        clean, report = run_dataset(spec, raw, parents, source_file)
        clean.to_csv(stage_dir / spec.name, index=False)
        reports.append(report)

        # Register referenceable keys for children's FK checks.
        provide = spec.provides_keys or ([spec.key] if spec.key else [])
        if provide:
            bucket = parents.setdefault(spec.role, {})
            for col in provide:
                if col in clean.columns:
                    bucket[col] = set(clean[col].dropna().astype(str))

    extra = _coverage_section(stage_dir)
    notes = render_cleaning_notes(slug, reports, [extra] if extra else None)
    (stage_dir / "CLEANING_NOTES.md").write_text(notes)

    print(f"\nStaged {len(reports)} datasets → {stage_dir}")
    for r in reports:
        removed = r.input_rows - r.output_rows
        print(f"  {r.dataset:42s} {r.input_rows:>8,} → {r.output_rows:>8,}  ({removed:,} removed)")
    print(f"  notes → {stage_dir / 'CLEANING_NOTES.md'}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean and stage raw source extracts.")
    parser.add_argument("--company", required=True, help="company slug, e.g. yumove")
    args = parser.parse_args()
    raise SystemExit(stage_company(args.company))


if __name__ == "__main__":
    main()
