"""Deterministic post-generation validation for raw source datasets.

Closed-loop check that generated raw extracts match the targets and data-issue
signatures documented in a company setup yaml. Run after raw-source generation
and before any standardization:

    python3 -m synthetic_pitch_data.validate_raw --company yumove

Exits non-zero if any check FAILs, so it can gate the workflow.

Generalising across companies
-----------------------------
Companies use different *subsets* of source systems, but each system has a
standard schema (canonical filenames + key columns) documented under
references/standard-source-schemas/. Key/FK relationships are therefore
properties of the *system*, not the company. `RAW_SCHEMA` below is that registry,
keyed by canonical filename and tagged with a logical `role` so checks survive
filename drift (e.g. GA4 "orders" vs "purchase_events"). The harness validates
only the files a company actually generated (its yaml `raw_extracts_to_build`
intersected with what's on disk). Adding a company that reuses known systems
needs no code change; a brand-new system type needs one registry entry, reused
by every future company.

Metric formulas follow references/metric-definitions.md (AOV = mean(total_price),
net of discount, VAT-inclusive, shipping-excluded; monthly volume targets are
promo-inclusive).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .paths import REPO_ROOT, SOURCE_ROOT

SETUP_DIR = REPO_ROOT / "skills" / "company-synthetic-data-workflow" / "assets" / "company-setups"

# Schema registry, keyed by canonical raw filename. One entry per known standard
# source extract, shared across all companies that use that system.
#   role       : logical role, used to resolve cross-file references and let
#                checks tolerate filename variants (multiple files may share a role)
#   pk         : column expected unique within the file
#   ts         : ISO-ish timestamp column for window checks
#   fks        : list of (child_col, parent_role, parent_col)
#   plus per-role column hints consumed by specific checks (revenue_col, etc.)
RAW_SCHEMA: dict[str, dict] = {
    # --- Shopify --------------------------------------------------------
    "shopify_customers.csv": {"role": "customers", "pk": "id", "email_col": "email"},
    "shopify_orders.csv": {
        "role": "orders",
        "pk": "id",
        "ts": "created_at",
        "revenue_col": "total_price",
        "order_name_col": "name",
        "fks": [("customer_id", "customers", "id")],
    },
    "shopify_order_items.csv": {
        "role": "order_items",
        "fks": [("order_id", "orders", "id"), ("product_id", "products", "product_id")],
    },
    "shopify_products.csv": {"role": "products", "pk": "variant_id"},
    # --- GA4 (filename varies by export query) --------------------------
    "ga4_reporting_purchase_events.csv": {
        "role": "ga4_events",
        "ts_compact": "dateHourMinute",
        "channel_col": "defaultChannelGroup",
        "date_col": "date",
        "fks": [("transactionId", "orders", "id")],
    },
    "ga4_reporting_orders.csv": {
        "role": "ga4_events",
        "ts_compact": "dateHourMinute",
        "channel_col": "defaultChannelGroup",
        "date_col": "date",
        "fks": [("transactionId", "orders", "id")],
    },
    # --- Triple Whale (filename varies) ---------------------------------
    "triple_whale_attributed_orders.csv": {
        "role": "attribution_orders",
        "channel_col": "channel",
        "fks": [("order_id", "orders", "id")],
    },
    "triplewhale_customer_journey_attribution_orders.csv": {
        "role": "attribution_orders",
        "channel_col": "channel",
        "fks": [("order_id", "orders", "id")],
    },
    # --- OrderGroove ----------------------------------------------------
    "ordergroove_subscriptions.csv": {"role": "subscriptions", "pk": "publicId"},
    "ordergroove_subscription_orders.csv": {"role": "subscription_orders", "pk": "publicId"},
    # --- CRM / support --------------------------------------------------
    "bloomreach_campaign_events.csv": {"role": "crm_events", "ts": "timestamp"},
    "klaviyo_events.csv": {"role": "crm_events", "pk": "event_id", "ts": "timestamp"},
    "zendesk_tickets.csv": {"role": "support_tickets", "pk": "id", "ts": "created_at"},
    # --- Custom Postgres ------------------------------------------------
    "user.csv": {"role": "customers", "pk": "user_id", "email_col": "email"},
    "fact_order.csv": {
        "role": "orders",
        "pk": "order_id",
        "ts": "ordered_at",
        "revenue_col": "net_sale_price",
        "fks": [("user_id", "customers", "user_id")],
    },
}


@dataclass
class Result:
    name: str
    status: str  # PASS | FAIL | WARN | MANUAL | SKIP
    detail: str


class Validator:
    def __init__(self, slug: str):
        self.slug = slug
        setup_path = SETUP_DIR / f"{slug}.yaml"
        if not setup_path.exists():
            raise SystemExit(f"No setup yaml at {setup_path}")
        self.cfg = yaml.safe_load(setup_path.read_text())
        self.src = SOURCE_ROOT / slug
        if not self.src.exists():
            raise SystemExit(f"No generated data at {self.src}")
        self._cache: dict[str, pd.DataFrame] = {}
        self.results: list[Result] = []
        self.scale = float(
            (self.cfg.get("volume_plan", {}).get("reduction_actions", {}) or {}).get(
                "row_volume_scaling_factor"
            )
            or 1.0
        )
        self.tests = {
            t["name"]: (t.get("threshold") or {})
            for t in self.cfg.get("execution_plan", {}).get("validation_tests", [])
        }
        # Accepted waivers: checks whose FAIL is a known, signed-off deviation.
        # They report WAIVED (not FAIL) so a deferred issue doesn't block the gate.
        self.waivers = {
            w["check"]: w.get("reason", "")
            for w in self.cfg.get("execution_plan", {}).get("accepted_waivers", []) or []
        }
        # Files this company actually produced that we know how to validate.
        self.present = {f.name for f in self.src.glob("*.csv") if f.name in RAW_SCHEMA}
        self.by_role: dict[str, str] = {}
        for fname in self.present:
            role = RAW_SCHEMA[fname].get("role")
            self.by_role.setdefault(role, fname)

    # ---- data access -----------------------------------------------------
    def df(self, name: str) -> pd.DataFrame | None:
        if name not in self._cache:
            path = self.src / name
            self._cache[name] = (
                pd.read_csv(path, dtype=str, keep_default_na=False) if path.exists() else None
            )
        return self._cache[name]

    def role_file(self, role: str) -> str | None:
        return self.by_role.get(role)

    def role_df(self, role: str) -> pd.DataFrame | None:
        fname = self.role_file(role)
        return self.df(fname) if fname else None

    def role_attr(self, role: str, key: str):
        fname = self.role_file(role)
        return RAW_SCHEMA[fname].get(key) if fname else None

    def add(self, name: str, status: str, detail: str) -> None:
        if status == "FAIL" and name in self.waivers:
            reason = self.waivers[name]
            detail = f"{detail}  [WAIVED: {reason}]" if reason else f"{detail}  [WAIVED]"
            status = "WAIVED"
        self.results.append(Result(name, status, detail))

    @staticmethod
    def _date(value) -> str | None:
        return str(value) if value else None

    # ---- structural checks ----------------------------------------------
    def check_expected_extracts(self) -> None:
        expected = self.cfg.get("generation", {}).get("raw_extracts_to_build") or []
        if not expected:
            self.add("expected_extracts_present", "SKIP", "no raw_extracts_to_build in yaml")
            return
        on_disk = {f.name for f in self.src.glob("*.csv")}
        missing = [e for e in expected if e not in on_disk]
        self.add(
            "expected_extracts_present",
            "FAIL" if missing else "PASS",
            f"missing: {', '.join(missing)}" if missing else f"all {len(expected)} extracts present",
        )

    def check_primary_keys(self) -> None:
        problems, checked = [], 0
        for fname in sorted(self.present):
            col = RAW_SCHEMA[fname].get("pk")
            if not col:
                continue
            df = self.df(fname)
            if df is None or col not in df.columns:
                continue
            checked += 1
            dupes = len(df) - df[col].nunique()
            if dupes:
                problems.append(f"{fname}.{col}: {dupes} dupes")
        if not checked:
            self.add("primary_key_uniqueness", "SKIP", "no keyed files present")
        else:
            self.add(
                "primary_key_uniqueness",
                "FAIL" if problems else "PASS",
                "; ".join(problems) if problems else f"{checked} files, all PKs unique",
            )

    def check_foreign_keys(self) -> None:
        problems, checked = [], 0
        for fname in sorted(self.present):
            child = self.df(fname)
            if child is None:
                continue
            for child_c, parent_role, parent_c in RAW_SCHEMA[fname].get("fks", []):
                parent = self.role_df(parent_role)
                if parent is None or child_c not in child.columns or parent_c not in parent.columns:
                    continue
                checked += 1
                parent_ids = set(parent[parent_c])
                vals = child[child_c][child[child_c] != ""]
                orphan = int((~vals.isin(parent_ids)).sum())
                if orphan:
                    problems.append(f"{fname}.{child_c}->{parent_role}.{parent_c}: {orphan} orphans")
        if not checked:
            self.add("foreign_key_reconciliation", "SKIP", "no resolvable FK edges present")
        else:
            self.add(
                "foreign_key_reconciliation",
                "FAIL" if problems else "PASS",
                "; ".join(problems) if problems else f"{checked} edges reconcile",
            )

    def check_window_bounds(self) -> None:
        th = self.tests.get("modeling_window_bounds", {})
        start, end = self._date(th.get("window_start")), self._date(th.get("window_end"))
        orders = self.role_df("orders")
        ts = self.role_attr("orders", "ts")
        if not (start and end) or orders is None or not ts:
            self.add("modeling_window_bounds", "SKIP", "no window dates or no orders timeline")
            return
        d = orders[ts].str.slice(0, 10)
        out = int(((d < start) | (d > end)).sum())
        self.add(
            "modeling_window_bounds",
            "FAIL" if out else "PASS",
            f"{out} orders outside [{start}, {end}]" if out else f"all within [{start}, {end}]",
        )

    def check_source_windows(self) -> None:
        th = self.tests.get("source_specific_window_bounds", {})
        earliest_by_file = th.get("earliest_by_file") or {}
        if not earliest_by_file:
            self.add("source_specific_window_bounds", "SKIP", "no earliest_by_file map in yaml")
            return
        problems, checked = [], 0
        for fname, start in earliest_by_file.items():
            df = self.df(fname)
            entry = RAW_SCHEMA.get(fname, {})
            col = entry.get("ts") or entry.get("date_col") or "created_at"
            if df is None or col not in df.columns:
                continue
            checked += 1
            earliest = df[col].str.slice(0, 10).min()
            if earliest < self._date(start):
                problems.append(f"{fname}: earliest {earliest} < {start}")
        if not checked:
            self.add("source_specific_window_bounds", "SKIP", "no listed files present")
        else:
            self.add(
                "source_specific_window_bounds",
                "FAIL" if problems else "PASS",
                "; ".join(problems) if problems else f"{checked} source windows respected",
            )

    def check_ga4_alignment(self) -> None:
        ga = self.role_df("ga4_events")
        orders = self.role_df("orders")
        ts_compact = self.role_attr("ga4_events", "ts_compact")
        orders_ts = self.role_attr("orders", "ts")
        orders_pk = self.role_attr("orders", "pk")
        if ga is None or orders is None or not (ts_compact and orders_ts and orders_pk):
            self.add("ga4_order_timestamp_alignment", "SKIP", "no GA4/orders or missing columns")
            return
        # GA4 transactionId joins to the orders pk.
        fk_col = next(
            (c for c, role, _ in RAW_SCHEMA[self.role_file("ga4_events")].get("fks", []) if role == "orders"),
            "transactionId",
        )
        tol = self.tests.get("ga4_order_timestamp_alignment", "30_minutes")
        tol_min = int(str(tol).split("_")[0]) if tol else 30
        o_ts = pd.to_datetime(orders.set_index(orders_pk)[orders_ts], utc=True, errors="coerce")
        g = ga[[fk_col, ts_compact]].copy()
        g["gts"] = pd.to_datetime(g[ts_compact], format="%Y%m%d%H%M", utc=True, errors="coerce")
        g["ots"] = g[fk_col].map(o_ts)
        matched = g.dropna(subset=["gts", "ots"])
        if matched.empty:
            self.add("ga4_order_timestamp_alignment", "SKIP", "no matched GA4 events")
            return
        diff_min = (matched["gts"] - matched["ots"]).abs().dt.total_seconds() / 60
        breaches = int((diff_min > tol_min).sum())
        self.add(
            "ga4_order_timestamp_alignment",
            "FAIL" if breaches else "PASS",
            f"{breaches}/{len(matched)} events >{tol_min}min from order"
            if breaches
            else f"all {len(matched)} matched events within {tol_min}min",
        )

    # ---- metric trajectory ----------------------------------------------
    def _metric_trajectory(self) -> dict:
        if "metric_trajectory" in self.cfg:
            return self.cfg["metric_trajectory"] or {}
        return (self.cfg.get("research", {}) or {}).get("metric_trajectory", {}) or {}

    def _series(self, key: str, value_field: str) -> dict[str, float]:
        out = {}
        for row in self._metric_trajectory().get(key, []) or []:
            out[str(row["period"])] = float(row[value_field])
        return out

    def check_metric_trajectory(self) -> None:
        orders = self.role_df("orders")
        ts = self.role_attr("orders", "ts")
        rev_col = self.role_attr("orders", "revenue_col")
        if orders is None or not ts:
            self.add("metric_trajectory_alignment", "SKIP", "no orders timeline")
            return
        th = self.tests.get("metric_trajectory_alignment", {})
        orders_pct = float(th.get("orders_pct", 3))
        revenue_pct = float(th.get("revenue_pct", 6))
        aov_pct = float(th.get("aov_pct", 4))

        m = orders[ts].str.slice(0, 7)
        cnt = m.value_counts().to_dict()
        if rev_col and rev_col in orders.columns:
            price = pd.to_numeric(orders[rev_col], errors="coerce")
            rev = price.groupby(m).sum().to_dict()
            aov = price.groupby(m).mean().to_dict()
        else:
            rev, aov = {}, {}

        def worst(target: dict, actual: dict, scale: float):
            worst_dev, worst_label = 0.0, ""
            for period, tgt in sorted(target.items()):
                exp = tgt * scale
                if exp == 0:
                    continue
                dev = abs(actual.get(period, 0) - exp) / exp * 100
                if dev > worst_dev:
                    worst_dev, worst_label = dev, f"{period}: {actual.get(period, 0):,.0f} vs {exp:,.0f}"
            return worst_dev, worst_label

        for label, target, actual, scale, tol in [
            ("orders", self._series("orders_by_period", "orders"), cnt, self.scale, orders_pct),
            ("revenue", self._series("revenue_by_period", "revenue"), rev, self.scale, revenue_pct),
            ("AOV", self._series("aov_by_period", "aov"), aov, 1.0, aov_pct),
        ]:
            if not target:
                self.add(f"metric_trajectory:{label}", "SKIP", "no targets in yaml")
                continue
            if not actual:
                self.add(f"metric_trajectory:{label}", "SKIP", "no revenue column on orders file")
                continue
            dev, where = worst(target, actual, scale)
            self.add(
                f"metric_trajectory:{label}",
                "FAIL" if dev > tol else "PASS",
                f"worst dev {dev:.1f}% (tol {tol:.0f}%)" + (f" @ {where}" if where else ""),
            )

    # ---- data-issue signatures ------------------------------------------
    @staticmethod
    def _in_range(value: float, rng) -> bool:
        return rng[0] <= value <= rng[1]

    def check_data_issues(self) -> None:
        registry = {
            "email_casing_or_whitespace_drift": self._issue_email_drift,
            "partial_attribution_coverage": self._issue_partial_attribution,
            "channel_tracking_break": self._issue_channel_break,
            "near_duplicate_orders": self._issue_near_duplicate_orders,
        }
        for issue in self.cfg.get("data_issues", {}).get("selected", []):
            check = issue.get("check")
            label = issue.get("issue", check or "?")
            if not check:
                self.add(f"data_issue:{label}", "MANUAL", "no automated check declared")
                continue
            fn = registry.get(check)
            if fn is None:
                self.add(f"data_issue:{label}", "MANUAL", f"no registered check '{check}'")
                continue
            rng = issue.get("expected_prevalence_range")
            fn(label, tuple(rng) if rng else None)

    def _issue_email_drift(self, label, rng):
        df = self.role_df("customers")
        col = self.role_attr("customers", "email_col")
        if df is None or not col or col not in df.columns:
            return self.add(f"data_issue:{label}", "SKIP", "no customers email column")
        emails = df[col][df[col] != ""]
        share = float((emails != emails.str.strip().str.lower()).mean())
        ok = self._in_range(share, rng) if rng else share > 0
        self.add(
            f"data_issue:{label}",
            "PASS" if ok else "FAIL",
            f"{share:.2%} drifted" + (f" (expected {rng[0]:.0%}-{rng[1]:.0%})" if rng else ""),
        )

    def _issue_partial_attribution(self, label, rng):
        orders = self.role_df("orders")
        attr = self.role_df("attribution_orders")
        orders_pk = self.role_attr("orders", "pk")
        orders_ts = self.role_attr("orders", "ts")
        if orders is None or attr is None or not orders_pk:
            return self.add(f"data_issue:{label}", "SKIP", "no orders or attribution source")
        attr_file = self.role_file("attribution_orders")
        fk_col = next(
            (c for c, role, _ in RAW_SCHEMA[attr_file].get("fks", []) if role == "orders"),
            "order_id",
        )
        start = self.tests.get("source_specific_window_bounds", {}).get("earliest_by_file", {}).get(attr_file)
        in_win = orders
        if start and orders_ts:
            in_win = orders[orders[orders_ts].str.slice(0, 10) >= self._date(start)]
        covered = float(in_win[orders_pk].isin(set(attr[fk_col])).mean())
        gap = 1 - covered
        ok = self._in_range(gap, rng) if rng else gap > 0
        self.add(
            f"data_issue:{label}",
            "PASS" if ok else "FAIL",
            f"{gap:.2%} of in-window orders missing from {attr_file}"
            + (f" (expected {rng[0]:.0%}-{rng[1]:.0%})" if rng else ""),
        )

    def _issue_channel_break(self, label, rng):
        ga = self.role_df("ga4_events")
        date_col = self.role_attr("ga4_events", "date_col")
        chan_col = self.role_attr("ga4_events", "channel_col")
        if ga is None or not (date_col and chan_col):
            return self.add(f"data_issue:{label}", "SKIP", "no GA4 channel data")
        by_day = ga[chan_col].eq("Unassigned").groupby(ga[date_col]).mean()
        baseline, peak = float(by_day.median()), float(by_day.max())
        ok = baseline <= 0.12 and peak >= 0.18
        self.add(
            f"data_issue:{label}",
            "PASS" if ok else "FAIL",
            f"baseline(median) {baseline:.1%}, peak {peak:.1%} (want baseline<=12%, peak>=18%)",
        )

    def _issue_near_duplicate_orders(self, label, rng):
        orders = self.role_df("orders")
        col = self.role_attr("orders", "order_name_col")
        if orders is None or not col or col not in orders.columns:
            return self.add(f"data_issue:{label}", "SKIP", "no order-name column")
        share = 1 - orders[col].nunique() / len(orders)
        ok = self._in_range(share, rng) if rng else 0 < share < 0.01
        self.add(
            f"data_issue:{label}",
            "PASS" if ok else "FAIL",
            f"{share:.3%} duplicate order names"
            + (f" (expected {rng[0]:.2%}-{rng[1]:.2%})" if rng else ""),
        )

    # ---- driver ----------------------------------------------------------
    def run(self) -> int:
        self.check_expected_extracts()
        self.check_primary_keys()
        self.check_foreign_keys()
        self.check_window_bounds()
        self.check_source_windows()
        self.check_ga4_alignment()
        self.check_metric_trajectory()
        self.check_data_issues()

        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "MANUAL": "📝", "WAIVED": "🟡", "SKIP": "··"}
        print(f"\nValidation report — {self.slug}  (scale {self.scale})")
        print(f"systems detected: {', '.join(sorted(self.by_role))}")
        print("=" * 72)
        for r in self.results:
            print(f"  {icon.get(r.status, '?')} {r.status:6s} {r.name:34s} {r.detail}")
        fails = [r for r in self.results if r.status == "FAIL"]
        waived = [r for r in self.results if r.status == "WAIVED"]
        manual = [r for r in self.results if r.status == "MANUAL"]
        passes = sum(1 for r in self.results if r.status == "PASS")
        print("=" * 72)
        print(
            f"  {len(fails)} FAIL, {len(waived)} WAIVED, {len(manual)} MANUAL, "
            f"{passes} PASS of {len(self.results)} checks"
        )
        if waived:
            print("  WAIVED checks are accepted known deviations (see execution_plan.accepted_waivers).")
        if manual:
            print("  MANUAL checks require human sense-check (no automated signature).")
        return 1 if fails else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated raw source data.")
    parser.add_argument("--company", required=True, help="company slug, e.g. yumove")
    args = parser.parse_args()
    sys.exit(Validator(args.company).run())


if __name__ == "__main__":
    main()
