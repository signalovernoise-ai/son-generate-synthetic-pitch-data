"""Raw source generator for Fussy.

Builds the Shopify commerce spine (products -> orders -> customers -> order_items) plus
Recharge (subscriptions + charges), GA4, Klaviyo, Google Ads and Gorgias.

Two things drive this generator and differ from previous companies:

1. **The refill cadence.** Subscribe & Save ships a starter pack, then the first refill
   delivery a month later, then a rolling 3-monthly supply. Renewals therefore land at months
   1, 4, 7, 10, 13 from the first order, which produces a sawtooth cohort-retention curve
   rather than a smooth decay. Renewals that would overshoot a month's order target are
   *skipped* to the next cycle (Recharge skip/delay), never dropped.

2. **AOV calibration on a multi-price catalog.** Order counts are pinned to
   MONTHLY_ORDER_TARGETS, then each month's baskets are built base-first and the residual to
   the month's revenue target is closed symmetrically: a shortfall is filled with add-on lines,
   an overshoot with a promotional line discount on non-renewal orders. Targets are net of
   discount, VAT-inclusive and shipping-excluded per references/metric-definitions.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from synthetic_pitch_data.company.fussy.config import (
    ADHOC_REPEAT_SHARE,
    BUSINESS,
    CANCEL_LAG_RATE,
    DUPLICATE_ORDER_NAME_RATE,
    EMAIL_DRIFT_RATE,
    GA4_RENEWAL_CAPTURE,
    GA4_WEB_LOSS,
    GOOGLE_ADS_START,
    GORGIAS_NO_CUSTOMER_RATE,
    GORGIAS_NO_ORDER_RATE,
    KLAVIYO_START,
    MIN_NEW_SHARE,
    MONTHLY_AOV,
    MONTHLY_ORDER_TARGETS,
    MONTHLY_REFUND_RATE,
    MONTHLY_SUB_CROSSSELL,
    PRODUCTS,
    RENEWAL_SURVIVAL,
    RENEWAL_SURVIVAL_TAIL,
    ROW_SCALE,
    SEED,
    SHIPPING_FIRST_SUB,
    SHIPPING_STANDARD,
    SHIPPING_SUBSCRIPTION,
    SOURCE_WINDOW_END,
    SOURCE_WINDOW_START,
    SUBSCRIPTION_DISCOUNT,
    SUB_TAKE_RATE,
    SUB_TAKE_RATE_BLACK_FRIDAY,
    TEST_ORDER_RATE,
    TRACKING_BREAKS,
    UNATTRIBUTED_BASELINE,
    VAT_RATE,
)
from synthetic_pitch_data.paths import ensure_workspace_dirs
from synthetic_pitch_data.raw_common import print_source_summary, write_source_csv


FIRST_NAMES = [
    "Emily", "Sophie", "Charlotte", "Olivia", "Amelia", "Jessica", "Hannah", "Grace",
    "James", "Oliver", "Harry", "Jack", "Thomas", "George", "Daniel", "Ben",
    "Freya", "Isla", "Ruby", "Alex",
]

LAST_NAMES = [
    "Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Davies", "Evans",
    "Thomas", "Roberts", "Walker", "Wright", "Robinson", "Thompson", "Clarke",
]

# (city, county, county_code)
CITIES = [
    ("London", "Greater London", "LND"),
    ("Manchester", "Greater Manchester", "MAN"),
    ("Birmingham", "West Midlands", "WMD"),
    ("Bristol", "Bristol, City of", "BST"),
    ("Leeds", "West Yorkshire", "WYK"),
    ("Glasgow", "Glasgow City", "GLG"),
    ("Edinburgh", "City of Edinburgh", "EDH"),
    ("Brighton", "East Sussex", "ESX"),
    ("Cardiff", "Cardiff", "CRF"),
    ("Nottingham", "Nottinghamshire", "NTT"),
]

POSTCODE_AREAS = ["E", "SE", "SW", "N", "NW", "M", "B", "BS", "LS", "G", "EH", "BN", "CF", "NG"]

EMAIL_DOMAINS = ["gmail.com", "outlook.com", "hotmail.co.uk", "yahoo.co.uk", "icloud.com"]

# Acquisition channels for a paid-led UK D2C personal-care brand.
# channel_group, source, medium, source_platform
CH_PAID_SOCIAL = ("Paid Social", "facebook", "paid_social", "Meta")
CH_PAID_SEARCH = ("Paid Search", "google", "cpc", "Google Ads")
CH_ORGANIC = ("Organic Search", "google", "organic", "Google")
CH_DIRECT = ("Direct", "(direct)", "(none)", "Direct")
CH_EMAIL = ("Email", "klaviyo", "email", "Klaviyo")
CH_AFFILIATE = ("Affiliate", "awin", "affiliate", "Awin")
CH_REFERRAL = ("Referral", "referral", "referral", "Referral")

CHANNELS = [CH_PAID_SOCIAL, CH_PAID_SEARCH, CH_ORGANIC, CH_DIRECT, CH_EMAIL, CH_AFFILIATE, CH_REFERRAL]
# Normalised over attributed channels; the ~8% unattributed floor is applied separately in GA4
# so the baseline is not double-counted (see references/channel-mix-benchmarks.md).
CHANNEL_WEIGHTS = [0.28, 0.20, 0.13, 0.12, 0.10, 0.07, 0.02]

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge"]
DEVICES = ["mobile", "desktop", "tablet"]

MONTH_KEYS = [str(m) for m in pd.period_range(SOURCE_WINDOW_START, SOURCE_WINDOW_END, freq="M")]
MONTH_INDEX = {m: i for i, m in enumerate(MONTH_KEYS)}
WINDOW_START_TS = pd.Timestamp(SOURCE_WINDOW_START, tz="UTC")
WINDOW_END_TS = pd.Timestamp(SOURCE_WINDOW_END + " 23:59:59", tz="UTC")
KLAVIYO_START_TS = pd.Timestamp(KLAVIYO_START, tz="UTC")
NOW = pd.Timestamp("2026-08-06", tz="UTC")

# Renewal cadence: first refill delivery 1 month after the starter, then every 3 months.
FIRST_RENEWAL_GAP = 1
RENEWAL_GAP = 3

SUB_REFILL_UNIT = 5.00     # subscription price per deodorant refill (£15 per 3-refill delivery)
SUB_REFILL_QTY = 3


# --------------------------------------------------------------------------- helpers
def to_iso(ts: pd.Timestamp) -> str:
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def month_start(month_key: str) -> pd.Timestamp:
    return pd.Timestamp(f"{month_key}-01", tz="UTC")


def month_end(month_key: str) -> pd.Timestamp:
    return (month_start(month_key) + pd.offsets.MonthEnd(0)).tz_convert("UTC")


def random_timestamp_in_month(rng: np.random.Generator, month_key: str) -> pd.Timestamp:
    start = month_start(month_key)
    end = month_end(month_key) + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)
    seconds = int((end - start).total_seconds())
    return start + pd.Timedelta(seconds=int(rng.integers(0, seconds + 1)))


def random_timestamp_after(rng: np.random.Generator, month_key: str, after: pd.Timestamp) -> pd.Timestamp:
    """A timestamp in `month_key` that does not precede `after` (so repeat orders never
    time-travel before the customer was created)."""
    start = max(month_start(month_key), after)
    end = month_end(month_key) + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)
    if start >= end:
        return end
    seconds = int((end - start).total_seconds())
    return start + pd.Timedelta(seconds=int(rng.integers(0, seconds + 1)))


def weighted_choice(rng, values, weights, size, replace=True):
    probs = np.array(weights, dtype=float)
    probs = probs / probs.sum()
    return rng.choice(values, size=size, replace=replace, p=probs)


def make_email(first_name, last_name, serial, rng) -> str:
    domain = EMAIL_DOMAINS[int(rng.integers(0, len(EMAIL_DOMAINS)))]
    slug = f"{first_name}.{last_name}.{serial}".replace(" ", "").lower()
    return f"{slug}@{domain}"


def drift_email(email: str, rng) -> str:
    variant = int(rng.integers(0, 3))
    if variant == 0:
        return email.upper()
    if variant == 1:
        return f" {email.lower()} "
    local, domain = email.split("@", 1)
    return f"{local.title()}@{domain}"


def postcode(rng) -> str:
    area = POSTCODE_AREAS[int(rng.integers(0, len(POSTCODE_AREAS)))]
    return f"{area}{int(rng.integers(1, 30))} {int(rng.integers(1, 9))}AB"


def slugify_title(value: str) -> str:
    slug = value.lower().replace("&", "and").replace("£", "").replace(",", "")
    slug = slug.replace("'", "").replace(".", "").replace("(", "").replace(")", "")
    return "-".join(slug.split())


# --------------------------------------------------------------------------- products
def _product_index() -> dict[str, dict]:
    out = {}
    for idx, spec in enumerate(PRODUCTS, start=1):
        out[spec.sku] = {
            "product_id": f"gid://shopify/Product/{4100000 + idx}",
            "variant_id": f"gid://shopify/ProductVariant/{6200000 + idx}",
            "idx": idx,
            "spec": spec,
        }
    return out


PRODUCT_IDX = _product_index()


def build_products() -> pd.DataFrame:
    rows = []
    for spec in PRODUCTS:
        meta = PRODUCT_IDX[spec.sku]
        launch_ts = pd.Timestamp(spec.launch_date, tz="UTC")
        retire_ts = pd.Timestamp(spec.retire_date, tz="UTC") if spec.retire_date else pd.NaT
        if launch_ts > NOW:
            status = "draft"
        elif pd.notna(retire_ts) and retire_ts < NOW:
            status = "archived"
        elif not spec.current and pd.isna(retire_ts):
            status = "archived"
        else:
            status = "active"
        rows.append(
            {
                "product_id": meta["product_id"],
                "admin_graphql_api_id": meta["product_id"],
                "title": spec.title,
                "handle": slugify_title(spec.title),
                "vendor": "Fussy",
                "product_type": spec.product_type,
                "status": status,
                "published_at": to_iso(launch_ts if launch_ts < NOW else NOW),
                "created_at": to_iso(launch_ts),
                "updated_at": to_iso(NOW),
                "variant_id": meta["variant_id"],
                "sku": spec.sku,
                "barcode": f"{5060000000000 + meta['idx']}",
                "option_1": "Default Title",
                "option_2": pd.NA,
                "option_3": pd.NA,
                "price": round(spec.base_price, 2),
                "compare_at_price": round(spec.compare_at_price, 2),
                "cost": round(spec.base_price * 0.31, 2),
                "inventory_quantity": int(1200 + meta["idx"] * 37),
                "is_current": spec.current,
            }
        )
    return pd.DataFrame(rows).drop(columns=["is_current"])


def _as_item(spec) -> dict:
    meta = PRODUCT_IDX[spec.sku]
    return {
        "product_id": meta["product_id"],
        "variant_id": meta["variant_id"],
        "sku": spec.sku,
        "title": spec.title,
        "product_type": spec.product_type,
        "role": spec.role,
        "base_price": spec.base_price,
        "subscription_eligible": spec.subscription_eligible,
    }


def _by_role_at(ts: pd.Timestamp) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for spec in PRODUCTS:
        launch_ts = pd.Timestamp(spec.launch_date, tz="UTC")
        retire_ts = pd.Timestamp(spec.retire_date, tz="UTC") if spec.retire_date else None
        if ts < launch_ts or (retire_ts is not None and ts > retire_ts):
            continue
        out.setdefault(spec.role, []).append(_as_item(spec))
    return out


# Catalogue availability only changes at month boundaries in this model, so cache per month.
_ROLE_CACHE: dict[str, dict[str, list[dict]]] = {}


def roles_for_month(month_key: str) -> dict[str, list[dict]]:
    if month_key not in _ROLE_CACHE:
        _ROLE_CACHE[month_key] = _by_role_at(month_start(month_key) + pd.Timedelta(days=14))
    return _ROLE_CACHE[month_key]


def pick_from_roles(rng, month_key: str, weighted_roles: list[tuple[str, float]]) -> dict:
    pools = roles_for_month(month_key)
    roles = [(r, w) for r, w in weighted_roles if pools.get(r)]
    probs = np.array([w for _, w in roles], dtype=float)
    probs = probs / probs.sum()
    role = roles[int(rng.choice(len(roles), p=probs))][0]
    pool = pools[role]
    return pool[int(rng.integers(0, len(pool)))]


NEW_ORDER_ROLES = [
    ("starter", 0.42), ("starter_le", 0.10), ("scent_pack", 0.13), ("mini", 0.14),
    ("refill_pack", 0.08), ("bw_starter", 0.07), ("hw_starter", 0.04), ("case", 0.02),
]
ADHOC_ORDER_ROLES = [
    ("refill_pack", 0.44), ("refill_single", 0.10), ("mini", 0.10), ("bw_refill", 0.09),
    ("hw_refill", 0.07), ("scent_pack", 0.06), ("case", 0.05), ("bodybar", 0.05),
    ("bottle", 0.04),
]
ADDON_ROLES = [
    ("mini", 0.26), ("refill_single", 0.22), ("bodybar", 0.14), ("case", 0.14),
    ("bottle", 0.14), ("giftcard", 0.10),
]
CROSSSELL_ROLES = [("bw_refill", 0.6), ("hw_refill", 0.4)]


# --------------------------------------------------------------------------- customers
@dataclass
class CustomerProfile:
    customer_id: str
    canonical_email: str
    first_name: str
    last_name: str
    created_at: pd.Timestamp
    updated_at: pd.Timestamp
    city: str
    county: str
    county_code: str
    postcode: str
    accepts_marketing: str | None
    acquisition_channel: str
    source: str
    medium: str
    source_platform: str
    promo_acquired: bool
    email_drift: bool
    legacy: bool


def create_customer_profile(rng, serial, created_at, promo_acquired, legacy=False) -> CustomerProfile:
    first_name = FIRST_NAMES[int(rng.integers(0, len(FIRST_NAMES)))]
    last_name = LAST_NAMES[int(rng.integers(0, len(LAST_NAMES)))]
    city, county, county_code = CITIES[int(rng.integers(0, len(CITIES)))]
    probs = np.array(CHANNEL_WEIGHTS, dtype=float)
    ch = CHANNELS[int(rng.choice(len(CHANNELS), p=probs / probs.sum()))]
    accepts = rng.choice(["true", "false", "blank"], p=[0.66, 0.27, 0.07])
    return CustomerProfile(
        customer_id=str(7100000 + serial),
        canonical_email=make_email(first_name, last_name, serial, rng),
        first_name=first_name,
        last_name=last_name,
        created_at=created_at,
        updated_at=created_at + pd.Timedelta(days=int(rng.integers(3, 180))),
        city=city,
        county=county,
        county_code=county_code,
        postcode=postcode(rng),
        accepts_marketing=None if accepts == "blank" else accepts,
        acquisition_channel=ch[0],
        source=ch[1],
        medium=ch[2],
        source_platform=ch[3],
        promo_acquired=promo_acquired,
        email_drift=bool(rng.random() < EMAIL_DRIFT_RATE),
        legacy=legacy,
    )


def build_shopify_customers(profiles: list[CustomerProfile], rng) -> pd.DataFrame:
    rows = []
    for p in profiles:
        display_email = drift_email(p.canonical_email, rng) if p.email_drift else p.canonical_email
        rows.append(
            {
                "id": p.customer_id,
                "email": display_email,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "phone": f"+447{int(rng.integers(100000000, 999999999))}",
                "created_at": to_iso(p.created_at),
                "updated_at": to_iso(max(p.updated_at, p.created_at)),
                "state": "enabled",
                "verified_email": True,
                "tax_exempt": False,
                "tags": "legacy" if p.legacy else "",
                "currency": "GBP",
                "accepts_marketing": p.accepts_marketing,
                "default_address_city": p.city,
                "default_address_province": p.county,
                "default_address_province_code": p.county_code,
                "default_address_country": "United Kingdom",
                "default_address_country_code": "GB",
                "default_address_zip": p.postcode,
            }
        )
    return pd.DataFrame(rows).sort_values("created_at").reset_index(drop=True)


# --------------------------------------------------------------------------- core spine
class Intent:
    """A planned order before AOV calibration decides add-ons or promo discount."""

    __slots__ = ("kind", "customer", "ts", "lines", "sub_group", "is_test", "welcome")

    def __init__(self, kind, customer, ts, lines, sub_group=None, is_test=False):
        self.kind = kind            # new | renewal | adhoc
        self.customer = customer
        self.ts = ts
        self.lines = lines          # list of (item, qty, unit_price)
        self.sub_group = sub_group
        self.is_test = is_test


def build_core_sources():
    """Subscription-cadence order engine.

    Each month's fixed order target is composed of (a) Recharge renewals from the surviving
    active base whose cycle falls due this month, (b) one-time repeat purchases from past
    buyers, and (c) new customers. Renewals beyond the month's capacity skip to the next
    cycle rather than disappearing, which is exactly what Recharge skip/delay does.
    """
    rng = np.random.default_rng(SEED)
    profiles: dict[str, CustomerProfile] = {}
    profile_list: list[CustomerProfile] = []
    active_subs: dict[int, dict] = {}
    all_subs: list[dict] = []
    repeat_pool: list[str] = []
    repeat_pool_seen: set[str] = set()

    order_rows: list[dict] = []
    line_rows: list[dict] = []
    charge_rows: list[dict] = []
    name_pool: list[str] = []
    cs = os_ = li = gid = chg = 1

    def new_profile(ts, promo_acquired=False, legacy=False):
        nonlocal cs
        p = create_customer_profile(rng, cs, ts, promo_acquired, legacy=legacy)
        cs += 1
        profiles[p.customer_id] = p
        profile_list.append(p)
        return p

    def open_subscription(customer, ts, midx, bf_cohort, month_key):
        nonlocal gid
        pools = roles_for_month(month_key)
        refill = (pools.get("refill_single") or pools["refill_pack"])[0]
        group = {
            "group_id": gid,
            "customer_id": customer.customer_id,
            "created_at": ts,
            "next_idx": midx + FIRST_RENEWAL_GAP,
            "cycle": 0,
            "bf_cohort": bf_cohort,
            "status": "active",
            "cancelled_at": None,
            "cancel_reason": "",
            "last_charge_ts": ts,
            "lines": [{"item": refill, "qty": SUB_REFILL_QTY, "unit_price": SUB_REFILL_UNIT}],
            "crosssell": False,
        }
        gid += 1
        active_subs[group["group_id"]] = group
        all_subs.append(group)
        return group

    def cancel_subscription(group):
        """Cancellation is recorded when the customer acts in the portal, which routinely
        lags the last successful charge (modelled data issue). Churned subscribers stay in
        the pool as candidates for later one-time repeat purchases."""
        lag_days = int(rng.integers(1, 20))
        if rng.random() < CANCEL_LAG_RATE:
            lag_days = int(rng.integers(38, 95))
        cancelled = group["last_charge_ts"] + pd.Timedelta(days=lag_days)
        group["status"] = "cancelled"
        group["cancelled_at"] = min(cancelled, WINDOW_END_TS)
        group["cancel_reason"] = str(
            weighted_choice(
                rng,
                ["Too much product", "Too expensive", "Switching scent", "No longer needed", ""],
                [0.34, 0.22, 0.14, 0.22, 0.08],
                1,
            )[0]
        )
        active_subs.pop(group["group_id"], None)
        if group["customer_id"] not in repeat_pool_seen:
            repeat_pool_seen.add(group["customer_id"])
            repeat_pool.append(group["customer_id"])

    # --- seed the pre-window population ------------------------------------------------
    t0_orders = int(round(MONTHLY_ORDER_TARGETS[MONTH_KEYS[0]] * ROW_SCALE))
    legacy_subs = int(round(3.05 * 0.52 * t0_orders))
    legacy_buyers = int(round(9.0 * ADHOC_REPEAT_SHARE * t0_orders))
    for _ in range(legacy_subs):
        age_months = int(rng.integers(1, 19))
        created = WINDOW_START_TS - pd.Timedelta(days=int(age_months * 30 + rng.integers(0, 28)))
        customer = new_profile(created, promo_acquired=False, legacy=True)
        group = open_subscription(customer, created, -age_months, False, MONTH_KEYS[0])
        group["cycle"] = min(6, max(1, age_months // RENEWAL_GAP))
        group["next_idx"] = int(rng.integers(0, RENEWAL_GAP))
        group["last_charge_ts"] = created + pd.Timedelta(days=int(age_months * 28))
    for _ in range(legacy_buyers):
        created = WINDOW_START_TS - pd.Timedelta(days=int(rng.integers(30, 700)))
        customer = new_profile(created, promo_acquired=False, legacy=True)
        repeat_pool.append(customer.customer_id)
        repeat_pool_seen.add(customer.customer_id)

    # --- monthly loop -------------------------------------------------------------------
    for midx, month_key in enumerate(MONTH_KEYS):
        target_orders = int(round(MONTHLY_ORDER_TARGETS[month_key] * ROW_SCALE))
        target_revenue = target_orders * MONTHLY_AOV[month_key]
        crosssell_rate = MONTHLY_SUB_CROSSSELL[month_key]
        is_black_friday = month_key.endswith("-11")
        pools = roles_for_month(month_key)
        intents: list[Intent] = []

        # 1. Renewals due this month, after applying per-cycle survival.
        due = [g for g in active_subs.values() if g["next_idx"] == midx]
        survivors = []
        for group in due:
            cycle = group["cycle"] + 1
            surv = RENEWAL_SURVIVAL.get(cycle, RENEWAL_SURVIVAL_TAIL)
            if group["bf_cohort"]:
                surv *= 0.94
            if rng.random() < surv:
                survivors.append(group)
            else:
                cancel_subscription(group)

        adhoc_target = int(round(ADHOC_REPEAT_SHARE * target_orders))
        min_new = max(1, int(round(MIN_NEW_SHARE * target_orders)))
        max_renewals = max(0, target_orders - min_new - adhoc_target)
        if len(survivors) > max_renewals:
            keep_idx = set(int(i) for i in rng.choice(len(survivors), size=max_renewals, replace=False))
            for i, group in enumerate(survivors):
                if i not in keep_idx:
                    group["next_idx"] = midx + 1  # skip this cycle (Recharge skip/delay)
            survivors = [g for i, g in enumerate(survivors) if i in keep_idx]

        for group in survivors:
            customer = profiles[group["customer_id"]]
            ts = random_timestamp_after(rng, month_key, customer.created_at)
            if not group["crosssell"] and crosssell_rate and rng.random() < crosssell_rate:
                extra = pick_from_roles(rng, month_key, CROSSSELL_ROLES)
                group["lines"].append(
                    {"item": extra, "qty": 1, "unit_price": round(extra["base_price"] * (1 - SUBSCRIPTION_DISCOUNT), 2)}
                )
                group["crosssell"] = True
            lines = [(ln["item"], ln["qty"], ln["unit_price"]) for ln in group["lines"]]
            intents.append(Intent("renewal", customer, ts, lines, sub_group=group))
            group["cycle"] += 1
            group["next_idx"] = midx + RENEWAL_GAP
            group["last_charge_ts"] = ts

        # 2. One-time repeat purchases from past buyers.
        adhoc_count = min(adhoc_target, max(0, target_orders - len(survivors) - min_new))
        if repeat_pool and adhoc_count > 0:
            picks = rng.choice(len(repeat_pool), size=adhoc_count, replace=True)
            for i in picks:
                customer = profiles[repeat_pool[int(i)]]
                ts = random_timestamp_after(rng, month_key, customer.created_at)
                item = pick_from_roles(rng, month_key, ADHOC_ORDER_ROLES)
                qty = 2 if item["role"].endswith("single") else 1
                intents.append(Intent("adhoc", customer, ts, [(item, qty, item["base_price"])]))
        else:
            adhoc_count = 0

        # 3. New customers fill the remainder; half start a Subscribe & Save plan.
        new_count = max(0, target_orders - len(survivors) - adhoc_count)
        take_rate = SUB_TAKE_RATE_BLACK_FRIDAY if is_black_friday else SUB_TAKE_RATE
        for _ in range(new_count):
            ts = random_timestamp_in_month(rng, month_key)
            subscribes = bool(rng.random() < take_rate)
            customer = new_profile(ts, promo_acquired=is_black_friday or subscribes)
            if subscribes:
                starter_pool = pools.get("starter_le") if rng.random() < 0.22 else None
                item = (starter_pool or pools["starter"])[
                    int(rng.integers(0, len(starter_pool or pools["starter"])))
                ]
                group = open_subscription(customer, ts, midx, is_black_friday, month_key)
                intents.append(Intent("new", customer, ts, [(item, 1, item["base_price"])], sub_group=group))
            else:
                item = pick_from_roles(rng, month_key, NEW_ORDER_ROLES)
                repeat_pool.append(customer.customer_id)
                repeat_pool_seen.add(customer.customer_id)
                intents.append(Intent("new", customer, ts, [(item, 1, item["base_price"])]))

        # 4. Test / internal orders (data issue) — flagged, then zeroed out below.
        for intent in intents:
            if rng.random() < TEST_ORDER_RATE:
                intent.is_test = True

        # 5. AOV calibration. Close the gap between the base baskets and the month's revenue
        #    target: a shortfall buys add-on lines, an overshoot applies a promo discount to
        #    non-renewal orders. Renewals are contractual and are never re-priced.
        live = [i for i in intents if not i.is_test]
        base_total = sum(qty * price for i in live for _, qty, price in i.lines)
        flexible = [i for i in live if i.kind != "renewal"]
        addon_pool = [p for role, _ in ADDON_ROLES for p in pools.get(role, [])]
        addon_mean = float(np.mean([p["base_price"] for p in addon_pool])) if addon_pool else 10.0
        gap = target_revenue - base_total
        promo_rate = 0.0
        addon_p = 0.0
        if flexible:
            if gap > 0:
                addon_p = min(0.90, gap / (len(flexible) * addon_mean))
            else:
                flex_total = sum(qty * price for i in flexible for _, qty, price in i.lines)
                promo_rate = min(0.35, -gap / flex_total) if flex_total else 0.0

        for intent in flexible:
            if addon_p and rng.random() < addon_p:
                extra = pick_from_roles(rng, month_key, ADDON_ROLES)
                intent.lines.append((extra, 1, extra["base_price"]))

        # 6. Materialise orders and line items.
        for intent in intents:
            customer = intent.customer
            is_renewal = intent.kind == "renewal"
            is_first_sub = intent.kind == "new" and intent.sub_group is not None
            discount_rate = 0.0 if (is_renewal or intent.is_test) else promo_rate
            order_id = str(5900000000 + os_)
            order_name = f"#FUS{300000 + os_}"
            if name_pool and rng.random() < DUPLICATE_ORDER_NAME_RATE:
                order_name = name_pool[int(rng.integers(0, len(name_pool)))]
            else:
                name_pool.append(order_name)

            gross = 0.0
            net = 0.0
            lines: list[dict] = []
            for item, qty, unit_price in intent.lines:
                list_price = float(item["base_price"])
                sell = round(unit_price * (1.0 - discount_rate), 2)
                if intent.is_test:
                    sell = 0.0
                gross += list_price * qty
                net += sell * qty
                subscribed = is_renewal or (is_first_sub and item["subscription_eligible"])
                lines.append(
                    {
                        "order_id": order_id,
                        "line_item_id": f"gid://shopify/LineItem/{8300000000 + li}",
                        "admin_graphql_api_id": f"gid://shopify/LineItem/{8300000000 + li}",
                        "product_id": item["product_id"],
                        "variant_id": item["variant_id"],
                        "sku": item["sku"],
                        "title": item["title"],
                        "variant_title": "Default Title",
                        "vendor": "Fussy",
                        "product_type": item["product_type"],
                        "quantity": int(qty),
                        "price": round(list_price, 2),
                        "discounted_price": sell,
                        "total_discount": round((list_price - sell) * qty, 2),
                        "taxable": True,
                        "requires_shipping": item["role"] != "giftcard",
                        "fulfillment_status": "fulfilled",
                        "selling_plan_name": "Subscribe & Save - every 3 months" if subscribed else pd.NA,
                        "selling_plan_id": (
                            f"sp_{hashlib.sha1(item['sku'].encode()).hexdigest()[:10]}" if subscribed else pd.NA
                        ),
                    }
                )
                li += 1

            total_price = round(net, 2)
            total_line_items_price = round(gross, 2)
            total_discounts = round(max(0.0, total_line_items_price - total_price), 2)
            total_tax = round(total_price * VAT_RATE / (1 + VAT_RATE), 2)
            if intent.is_test:
                shipping = 0.0
            elif is_first_sub:
                shipping = SHIPPING_FIRST_SUB
            elif is_renewal:
                shipping = SHIPPING_SUBSCRIPTION
            else:
                shipping = SHIPPING_STANDARD

            refund_rate = MONTHLY_REFUND_RATE[month_key] + (0.004 if customer.promo_acquired else 0.0)
            refund_status, refunded_amount, financial_status = "none", 0.0, "paid"
            if not intent.is_test and rng.random() < refund_rate:
                if rng.random() < 0.6:
                    refund_status, refunded_amount, financial_status = "full", total_price, "refunded"
                else:
                    refund_status, financial_status = "partial", "partially_refunded"
                    refunded_amount = 0.0 if rng.random() < 0.15 else round(total_price * rng.uniform(0.2, 0.7), 2)

            order_rows.append(
                {
                    "id": order_id,
                    "admin_graphql_api_id": f"gid://shopify/Order/{5900000000 + os_}",
                    "order_number": 300000 + os_,
                    "name": order_name,
                    "customer_id": customer.customer_id,
                    "email": (
                        f"qa.test.{os_}@getfussy.com" if intent.is_test else customer.canonical_email
                    ),
                    "created_at": to_iso(intent.ts),
                    "processed_at": to_iso(intent.ts + pd.Timedelta(minutes=int(rng.integers(1, 25)))),
                    "updated_at": to_iso(intent.ts + pd.Timedelta(hours=int(rng.integers(4, 120)))),
                    "currency": "GBP",
                    "presentment_currency": "GBP",
                    "financial_status": financial_status,
                    "fulfillment_status": "fulfilled",
                    "subtotal_price": total_price,
                    "total_discounts": total_discounts,
                    "total_tax": total_tax,
                    "total_shipping_price_set_amount": round(shipping, 2),
                    "total_price": total_price,
                    "total_line_items_price": total_line_items_price,
                    "taxes_included": True,
                    "total_weight": int(60 * sum(int(ln["quantity"]) for ln in lines)),
                    "line_items_count": int(sum(int(ln["quantity"]) for ln in lines)),
                    "billing_address_country": "United Kingdom",
                    "billing_address_country_code": "GB",
                    "billing_address_city": customer.city,
                    "billing_address_province": customer.county,
                    "billing_address_zip": customer.postcode,
                    "source_name": "internal" if intent.is_test else ("subscription_contract" if is_renewal else "web"),
                    "refunded_amount": round(refunded_amount, 2),
                    "refund_status": refund_status,
                }
            )
            line_rows.extend(lines)

            if intent.sub_group is not None:
                group = intent.sub_group
                charge_rows.append(
                    {
                        "id": str(4400000 + chg),
                        "subscription_id": str(2200000 + group["group_id"]),
                        "customer_id": str(3300000 + group["group_id"]),
                        "shopify_customer_id": customer.customer_id,
                        "shopify_order_id": order_id,
                        "type": "recurring" if is_renewal else "checkout",
                        "status": "success",
                        "scheduled_at": to_iso(intent.ts.normalize()),
                        "processed_at": to_iso(intent.ts),
                        "created_at": to_iso(intent.ts),
                        "updated_at": to_iso(intent.ts + pd.Timedelta(hours=int(rng.integers(1, 30)))),
                        "total_line_items_price": total_line_items_price,
                        "subtotal_price": total_price,
                        "total_discounts": total_discounts,
                        "total_tax": total_tax,
                        "shipping_price": round(shipping, 2),
                        "total_price": round(total_price + shipping, 2),
                        "currency": "GBP",
                        "number_times_tried": 1,
                        "retry_date": pd.NA,
                        "tags": "",
                    }
                )
                chg += 1
                # Dunning: a small share of recurring charges fail first and are retried.
                if is_renewal and rng.random() < 0.012 and intent.ts - pd.Timedelta(days=2) >= WINDOW_START_TS:
                    charge_rows.append(
                        {
                            "id": str(4400000 + chg),
                            "subscription_id": str(2200000 + group["group_id"]),
                            "customer_id": str(3300000 + group["group_id"]),
                            "shopify_customer_id": customer.customer_id,
                            "shopify_order_id": "",  # failed charge never created a Shopify order
                            "type": "recurring",
                            "status": "error",
                            "scheduled_at": to_iso((intent.ts - pd.Timedelta(days=2)).normalize()),
                            "processed_at": to_iso(intent.ts - pd.Timedelta(days=2)),
                            "created_at": to_iso(intent.ts - pd.Timedelta(days=2)),
                            "updated_at": to_iso(intent.ts - pd.Timedelta(days=1)),
                            "total_line_items_price": total_line_items_price,
                            "subtotal_price": total_price,
                            "total_discounts": total_discounts,
                            "total_tax": total_tax,
                            "shipping_price": round(shipping, 2),
                            "total_price": round(total_price + shipping, 2),
                            "currency": "GBP",
                            "number_times_tried": int(rng.integers(2, 4)),
                            "retry_date": to_iso(intent.ts.normalize()),
                            "tags": "dunning",
                        }
                    )
                    chg += 1
            os_ += 1

    customers_df = build_shopify_customers(profile_list, np.random.default_rng(SEED + 3))
    orders_df = pd.DataFrame(order_rows).sort_values("created_at").reset_index(drop=True)
    order_items_df = pd.DataFrame(line_rows).reset_index(drop=True)
    charges_df = pd.DataFrame(charge_rows).sort_values("created_at").reset_index(drop=True)
    subs_df = build_recharge_subscriptions(all_subs, profiles)
    return customers_df, orders_df, order_items_df, charges_df, subs_df, profiles, all_subs


def build_recharge_subscriptions(all_subs: list[dict], profiles: dict) -> pd.DataFrame:
    """One row per subscribed line (a customer with a cross-sell has two rows)."""
    rows = []
    for group in all_subs:
        customer = profiles[group["customer_id"]]
        base_created = group["created_at"]
        for line_no, line in enumerate(group["lines"]):
            item = line["item"]
            created = base_created if line_no == 0 else max(base_created, group["last_charge_ts"])
            next_charge = ""
            if group["status"] == "active":
                nxt = group["last_charge_ts"] + pd.Timedelta(days=RENEWAL_GAP * 30)
                next_charge = to_iso(nxt)
            rows.append(
                {
                    "id": f"{2200000 + group['group_id']}{line_no}",
                    "customer_id": str(3300000 + group["group_id"]),
                    "shopify_customer_id": customer.customer_id,
                    "address_id": str(5500000 + group["group_id"]),
                    "status": group["status"],
                    "created_at": to_iso(created),
                    "updated_at": to_iso(group["cancelled_at"] or group["last_charge_ts"]),
                    "cancelled_at": to_iso(group["cancelled_at"]) if group["cancelled_at"] is not None else "",
                    "cancellation_reason": group["cancel_reason"] if group["cancelled_at"] is not None else "",
                    "next_charge_scheduled_at": next_charge,
                    "order_interval_unit": "month",
                    "order_interval_frequency": RENEWAL_GAP,
                    "charge_interval_frequency": RENEWAL_GAP,
                    "order_day_of_month": int(created.day),
                    "quantity": int(line["qty"]),
                    "price": round(float(line["unit_price"]), 2),
                    "presentment_currency": "GBP",
                    "product_title": item["title"],
                    "variant_title": "Default Title",
                    "sku": item["sku"],
                    "shopify_product_id": item["product_id"],
                    "shopify_variant_id": item["variant_id"],
                    "is_prepaid": False,
                    "is_skippable": True,
                }
            )
    return pd.DataFrame(rows).sort_values("created_at").reset_index(drop=True)


# --------------------------------------------------------------------------- GA4
GA4_DIRECT = ("Direct", "Direct", "(direct)", "(none)", "Direct")
GA4_NOTSET = ("Unassigned", "Unassigned", "(not set)", "(not set)", "(not set)")


def _tracking_break_rate(day: pd.Timestamp) -> float | None:
    for start, days, rate in TRACKING_BREAKS:
        start_ts = pd.Timestamp(start, tz="UTC")
        if start_ts <= day < start_ts + pd.Timedelta(days=days):
            return rate
    return None


def build_ga4(orders, order_items, profiles, charges):
    """GA4 sees web checkouts only.

    Recharge recurring charges are created server-side with no browser session, so they almost
    never fire a web purchase event; the few that do carry Direct / (not set), never a paid
    channel. purchaseRevenue is reported shipping-inclusive, which is the documented revenue
    definition mismatch against the Shopify convention.
    """
    rng = np.random.default_rng(SEED + 11)
    renewal_order_ids = set(
        charges.loc[(charges["type"] == "recurring") & (charges["shopify_order_id"] != ""), "shopify_order_id"]
    )
    item_map = {str(oid): g.to_dict("records") for oid, g in order_items.groupby("order_id", sort=False)}
    order_rows, item_rows = [], []

    for order in orders.itertuples(index=False):
        if order.source_name == "internal":
            continue  # internal/test orders never reach the web pixel
        created = pd.Timestamp(order.created_at)
        is_renewal = str(order.id) in renewal_order_ids
        if is_renewal:
            if rng.random() >= GA4_RENEWAL_CAPTURE:
                continue
            ch = GA4_DIRECT if rng.random() < 0.80 else GA4_NOTSET
        else:
            if rng.random() < GA4_WEB_LOSS:
                continue
            break_rate = _tracking_break_rate(created.normalize())
            unattributed = break_rate if break_rate is not None else UNATTRIBUTED_BASELINE
            if rng.random() < unattributed:
                ch = GA4_NOTSET
            else:
                profile = profiles[str(order.customer_id)]
                ch = (
                    profile.acquisition_channel,
                    profile.acquisition_channel,
                    profile.source,
                    profile.medium,
                    profile.source_platform,
                )
        gts = created + pd.Timedelta(minutes=int(rng.integers(-18, 18)))
        gts = min(max(gts, WINDOW_START_TS), WINDOW_END_TS)
        items = item_map.get(str(order.id), [])
        gross_item = round(sum(float(i["price"]) * int(i["quantity"]) for i in items), 2)
        net_item = round(sum(float(i["discounted_price"]) * int(i["quantity"]) for i in items), 2)
        order_rows.append(
            {
                "date": gts.strftime("%Y%m%d"),
                "dateHour": gts.strftime("%Y%m%d%H"),
                "dateHourMinute": gts.strftime("%Y%m%d%H%M"),
                "transactionId": order.id,
                "defaultChannelGroup": ch[0],
                "sessionDefaultChannelGroup": ch[1],
                "source": ch[2],
                "medium": ch[3],
                "sourceMedium": f"{ch[2]} / {ch[3]}",
                "sourcePlatform": ch[4],
                "sessionSource": ch[2],
                "sessionMedium": ch[3],
                "sessionSourceMedium": f"{ch[2]} / {ch[3]}",
                "sessionSourcePlatform": ch[4],
                "browser": BROWSERS[int(rng.integers(0, len(BROWSERS)))],
                "deviceCategory": DEVICES[int(rng.integers(0, len(DEVICES)))],
                "platformDeviceCategory": DEVICES[int(rng.integers(0, len(DEVICES)))],
                "country": "United Kingdom",
                "region": order.billing_address_province,
                "city": order.billing_address_city,
                "streamId": "4471902288",
                "platform": "web",
                "user_id": order.customer_id if rng.random() < 0.88 else pd.NA,
                "itemPromotionId": pd.NA,
                "itemPromotionName": pd.NA,
                # GA4 reports revenue shipping-inclusive; Shopify total_price excludes it.
                "purchaseRevenue": round(order.total_price + order.total_shipping_price_set_amount, 2),
                "grossPurchaseRevenue": round(order.total_line_items_price + order.total_shipping_price_set_amount, 2),
                "shippingAmount": order.total_shipping_price_set_amount,
                "taxAmount": order.total_tax,
                "itemRevenue": net_item,
                "grossItemRevenue": gross_item,
                "transactions": 1,
                "ecommercePurchases": 1,
            }
        )
        for item in items:
            item_rows.append(
                {
                    "date": gts.strftime("%Y%m%d"),
                    "dateHour": gts.strftime("%Y%m%d%H"),
                    "dateHourMinute": gts.strftime("%Y%m%d%H%M"),
                    "transactionId": order.id,
                    "itemId": item["sku"],
                    "itemName": item["title"],
                    "itemBrand": "Fussy",
                    "itemVariant": "Default Title",
                    "itemCategory": item["product_type"],
                    "itemCategory2": pd.NA,
                    "itemCategory3": pd.NA,
                    "itemCategory4": pd.NA,
                    "itemCategory5": pd.NA,
                    "itemListId": "pdp",
                    "itemListName": "Product Detail Page",
                    "itemPromotionId": pd.NA,
                    "itemPromotionName": pd.NA,
                    "itemRevenue": round(float(item["discounted_price"]) * int(item["quantity"]), 2),
                    "grossItemRevenue": round(float(item["price"]) * int(item["quantity"]), 2),
                    "itemRefundAmount": (
                        round(order.refunded_amount / max(1, len(items)), 2) if order.refunded_amount else 0.0
                    ),
                    "itemDiscountAmount": round(float(item["total_discount"]), 2),
                    "itemsPurchased": int(item["quantity"]),
                    "itemPurchaseQuantity": int(item["quantity"]),
                }
            )
    return pd.DataFrame(order_rows), pd.DataFrame(item_rows)


# --------------------------------------------------------------------------- Klaviyo
def build_klaviyo_events(orders, profiles, charges):
    rng = np.random.default_rng(SEED + 23)
    renewal_order_ids = set(
        charges.loc[(charges["type"] == "recurring") & (charges["shopify_order_id"] != ""), "shopify_order_id"]
    )
    recent = orders[pd.to_datetime(orders["created_at"]) >= KLAVIYO_START_TS]
    rows = []
    eid = 1
    metric_ids = {
        "Received Email": "RXEM", "Opened Email": "OPEM", "Clicked Email": "CLEM",
        "Bounced Email": "BOEM", "Unsubscribed": "UNSB",
        "Received SMS": "RXSM", "Clicked SMS": "CLSM", "Placed Order": "PLOR",
    }
    flows = [
        ("Welcome Series", "flow_welcome"),
        ("Post-Purchase Nurture", "flow_postpurchase"),
        ("Refill Reminder", "flow_refillreminder"),
        ("Abandoned Checkout", "flow_abandoned"),
        ("Win-back", "flow_winback"),
    ]
    campaigns = [
        ("New Scent Drop", "cmp_scentdrop"),
        ("Plastic-Free July", "cmp_plasticfree"),
        ("Body Wash Launch", "cmp_bodywash"),
        ("Black Friday", "cmp_blackfriday"),
    ]

    def emit(profile, base_ts, metric, channel, flow=None, campaign=None, value=None, attributed_channel=None):
        nonlocal eid
        if base_ts < KLAVIYO_START_TS or base_ts > WINDOW_END_TS:
            return
        email = drift_email(profile.canonical_email, rng) if profile.email_drift else profile.canonical_email
        rows.append(
            {
                "event_id": f"01K{eid:012d}",
                "timestamp": to_iso(base_ts),
                "metric_id": metric_ids.get(metric, "MISC"),
                "metric_name": metric,
                "profile_id": f"prof_{profile.customer_id}",
                "email": email,
                "phone_number": f"+447{700000000 + int(profile.customer_id) % 99999999}" if channel == "sms" else pd.NA,
                "channel": channel,
                "$message": f"msg_{eid % 9000}",
                "campaign_id": campaign[1] if campaign else pd.NA,
                "campaign_name": campaign[0] if campaign else pd.NA,
                "$flow": flow[1] if flow else pd.NA,
                "$flow_message_id": f"{flow[1]}_m1" if flow else pd.NA,
                "flow_name": flow[0] if flow else pd.NA,
                "subject": "Time for a refill?" if channel == "email" else pd.NA,
                "$variation": pd.NA,
                "url": "https://www.getfussy.com/" if metric in ("Clicked Email", "Clicked SMS") else pd.NA,
                "bounce_type": pd.NA,
                "client_name": "Apple Mail" if metric == "Opened Email" else pd.NA,
                "client_type": "mobile" if metric == "Opened Email" else pd.NA,
                "num_segments": 1 if channel == "sms" else pd.NA,
                "$attributed_message": f"msg_{eid % 9000}" if metric == "Placed Order" else pd.NA,
                "$attributed_flow": flow[1] if (metric == "Placed Order" and flow) else pd.NA,
                "$attributed_channel": attributed_channel if metric == "Placed Order" else pd.NA,
                "$value": round(value, 2) if value is not None else pd.NA,
            }
        )
        eid += 1

    for order in recent.itertuples(index=False):
        if order.source_name == "internal":
            continue
        profile = profiles[str(order.customer_id)]
        if profile.accepts_marketing != "true" and rng.random() < 0.72:
            continue
        order_ts = pd.Timestamp(order.created_at)
        is_renewal = str(order.id) in renewal_order_ids
        flow = flows[2] if is_renewal else flows[1]
        base = order_ts + pd.Timedelta(hours=int(rng.integers(1, 40)))
        emit(profile, base, "Received Email", "email", flow=flow)
        if rng.random() < 0.49:
            emit(profile, base + pd.Timedelta(hours=int(rng.integers(1, 20))), "Opened Email", "email", flow=flow)
            if rng.random() < 0.28:
                emit(profile, base + pd.Timedelta(hours=int(rng.integers(2, 30))), "Clicked Email", "email", flow=flow)
        if rng.random() < 0.18:
            sbase = order_ts + pd.Timedelta(days=int(rng.integers(25, 70)))
            emit(profile, sbase, "Received SMS", "sms", flow=flows[2])
            if rng.random() < 0.13:
                emit(profile, sbase + pd.Timedelta(hours=int(rng.integers(1, 8))), "Clicked SMS", "sms", flow=flows[2])
        # Klaviyo tracks renewals server-side but must not credit them as click-driven.
        if not is_renewal and rng.random() < 0.13:
            emit(
                profile, order_ts, "Placed Order", "email", flow=flow,
                value=float(order.total_price),
                attributed_channel="email" if rng.random() < 0.72 else "sms",
            )

    marketable = [p for p in profiles.values() if p.accepts_marketing == "true"]
    for month_key in MONTH_KEYS:
        m_start = month_start(month_key)
        if m_start < KLAVIYO_START_TS or m_start > WINDOW_END_TS:
            continue
        campaign = campaigns[int(rng.integers(0, len(campaigns)))]
        sample = rng.choice(len(marketable), size=min(len(marketable), 9000), replace=False)
        send_ts = m_start + pd.Timedelta(days=int(rng.integers(2, 26)), hours=int(rng.integers(8, 18)))
        for i in sample:
            profile = marketable[int(i)]
            emit(profile, send_ts, "Received Email", "email", campaign=campaign)
            if rng.random() < 0.31:
                emit(profile, send_ts + pd.Timedelta(hours=int(rng.integers(1, 30))), "Opened Email", "email", campaign=campaign)
                if rng.random() < 0.16:
                    emit(profile, send_ts + pd.Timedelta(hours=int(rng.integers(2, 40))), "Clicked Email", "email", campaign=campaign)
            elif rng.random() < 0.02:
                emit(profile, send_ts + pd.Timedelta(minutes=int(rng.integers(1, 40))), "Unsubscribed", "email", campaign=campaign)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Google Ads
def build_google_ads():
    rng = np.random.default_rng(SEED + 41)
    start = pd.Timestamp(GOOGLE_ADS_START, tz="UTC")
    end = pd.Timestamp(SOURCE_WINDOW_END, tz="UTC")
    account_id, account_name = "6218849460", "Fussy"
    campaigns = [
        ("Brand - Fussy", "SEARCH", "TARGET_SPEND", 90),
        ("Non-Brand - Natural Deodorant", "SEARCH", "MAXIMIZE_CONVERSIONS", 420),
        ("Non-Brand - Refillable Deodorant", "SEARCH", "MAXIMIZE_CONVERSIONS", 260),
        ("Non-Brand - Aluminium Free", "SEARCH", "MAXIMIZE_CONVERSIONS", 180),
        ("Competitor", "SEARCH", "MAXIMIZE_CONVERSIONS", 90),
        ("Shopping - Deodorant", "SHOPPING", "MAXIMIZE_CONVERSION_VALUE", 340),
        ("Shopping - Body & Hand Wash", "SHOPPING", "MAXIMIZE_CONVERSION_VALUE", 150),
        ("Performance Max - Prospecting", "PERFORMANCE_MAX", "MAXIMIZE_CONVERSION_VALUE", 480),
        ("Performance Max - Retention", "PERFORMANCE_MAX", "MAXIMIZE_CONVERSION_VALUE", 160),
        ("Demand Gen - Sustainability", "DEMAND_GEN", "MAXIMIZE_CONVERSIONS", 120),
    ]
    rows = []
    for c_i, (cname, channel_type, bidding, base_spend) in enumerate(campaigns):
        campaign_id = f"{2210000000 + c_i}"
        c_start = start
        if "Body & Hand Wash" in cname:
            c_start = pd.Timestamp("2025-09-01", tz="UTC")
        for day in pd.date_range(c_start.normalize(), end.normalize(), freq="D", tz="UTC"):
            progress = (day - start).days / max(1, (end - start).days)
            season = 1.0
            if day.month in (6, 7):
                season = 1.15
            elif day.month == 11:
                season = 1.45
            elif day.month in (2, 9):
                season = 0.9
            spend = round(base_spend * (0.72 + 0.55 * progress) * season * float(rng.uniform(0.82, 1.18)), 2)
            if spend < 1:
                continue
            cost_micros = int(round(spend * 1_000_000))
            impressions = int(spend / float(rng.uniform(0.006, 0.020)))
            ctr_base = rng.uniform(0.05, 0.11) if cname.startswith("Brand") else rng.uniform(0.008, 0.030)
            clicks = max(1, int(impressions * float(ctr_base)))
            conversions = round(clicks * float(rng.uniform(0.04, 0.11)), 2)
            conv_value = round(conversions * float(rng.uniform(16.0, 24.0)), 2)
            rows.append(
                {
                    "segments.date": day.strftime("%Y-%m-%d"),
                    "customer.id": account_id,
                    "customer.descriptive_name": account_name,
                    "customer.currency_code": "GBP",
                    "campaign.id": campaign_id,
                    "campaign.name": cname,
                    "campaign.status": "ENABLED",
                    "campaign.advertising_channel_type": channel_type,
                    "campaign.bidding_strategy_type": bidding,
                    "metrics.impressions": impressions,
                    "metrics.clicks": clicks,
                    "metrics.cost_micros": cost_micros,
                    "metrics.conversions": conversions,
                    "metrics.conversions_value": conv_value,
                    "metrics.all_conversions": round(conversions * 1.18, 2),
                    "metrics.all_conversions_value": round(conv_value * 1.18, 2),
                    "metrics.ctr": round(clicks / impressions, 4) if impressions else 0.0,
                    "metrics.average_cpc": int(round(cost_micros / clicks)) if clicks else 0,
                    "metrics.average_cpm": int(round(cost_micros / impressions * 1000)) if impressions else 0,
                    "metrics.search_impression_share": (
                        round(float(rng.uniform(0.22, 0.71)), 4) if channel_type == "SEARCH" else pd.NA
                    ),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Gorgias
def build_gorgias_tickets(orders, profiles):
    """Order and customer linkage is agent-applied, so it is sparse by design."""
    rng = np.random.default_rng(SEED + 51)
    subjects = [
        ("Where is my refill delivery?", "shipping", "email"),
        ("How do I change my subscription frequency?", "subscription", "chat"),
        ("Cancel my subscription", "cancellation", "email"),
        ("My case button is stuck", "product_fault", "chat"),
        ("Can I swap my scent?", "subscription", "chat"),
        ("Is this suitable for sensitive skin?", "product_question", "email"),
        ("Refund request", "refund", "email"),
        ("Refill won't click into the case", "product_question", "instagram"),
    ]
    sample = orders[orders["source_name"] != "internal"].sample(frac=0.025, random_state=SEED).reset_index(drop=True)
    rows = []
    for idx, order in enumerate(sample.itertuples(index=False), start=1):
        profile = profiles[str(order.customer_id)]
        subject, tag, default_channel = subjects[int(rng.integers(0, len(subjects)))]
        created = pd.Timestamp(order.created_at) + pd.Timedelta(days=int(rng.integers(1, 21)))
        created = min(created, WINDOW_END_TS)
        closed = created + pd.Timedelta(hours=int(rng.integers(2, 120)))
        status = "open" if rng.random() < 0.16 else "closed"
        channel = default_channel if rng.random() < 0.8 else str(
            weighted_choice(rng, ["email", "chat", "sms", "facebook", "contact-form"], [0.4, 0.3, 0.1, 0.1, 0.1], 1)[0]
        )
        # Sparse commerce linkage: agents attach the order only some of the time, and chat /
        # social tickets often arrive from an address that matches no customer record.
        has_order = rng.random() >= GORGIAS_NO_ORDER_RATE
        has_customer = rng.random() >= GORGIAS_NO_CUSTOMER_RATE
        tags = f"{tag},vip" if rng.random() < 0.06 else tag
        if rng.random() < 0.05:
            tags = tags.upper()
        rows.append(
            {
                "id": str(9100000 + idx),
                "created_datetime": to_iso(created),
                "updated_datetime": to_iso(closed),
                "opened_datetime": to_iso(created),
                "closed_datetime": to_iso(closed) if status == "closed" else "",
                "status": status,
                "priority": str(weighted_choice(rng, ["normal", "high", "urgent"], [0.8, 0.17, 0.03], 1)[0]),
                "channel": channel,
                "via": "chat" if channel == "chat" else ("api" if channel in ("facebook", "instagram") else "email"),
                "subject": subject,
                "excerpt": f"Customer contacted us about {tag.replace('_', ' ')}.",
                "from_email": profile.canonical_email if has_customer else f"anon{idx}@mail-relay.example",
                "customer_id": str(6600000 + idx),
                "shopify_customer_id": order.customer_id if has_customer else "",
                "shopify_order_id": order.id if has_order else "",
                "assignee_user_id": str(770000 + int(rng.integers(1, 18))),
                "team_id": str(8800 + int(rng.integers(1, 4))),
                "tags": tags,
                "satisfaction_score": int(rng.integers(3, 6)) if (status == "closed" and rng.random() < 0.28) else "",
                "messages_count": int(rng.integers(2, 8)),
                "is_spam": False,
                "trashed_datetime": "",
                "language": "en",
            }
        )
    return pd.DataFrame(rows).sort_values("created_datetime").reset_index(drop=True)


# --------------------------------------------------------------------------- main
def write_outputs(output_map):
    for filename, df in output_map.items():
        path = write_source_csv(df, BUSINESS, filename)
        print_source_summary(f"{BUSINESS} {filename}", len(df), path)


def main() -> None:
    ensure_workspace_dirs()
    products_df = build_products()
    (
        customers_df,
        orders_df,
        order_items_df,
        charges_df,
        subs_df,
        profiles,
        _all_subs,
    ) = build_core_sources()
    ga4_orders_df, ga4_items_df = build_ga4(orders_df, order_items_df, profiles, charges_df)
    klaviyo_df = build_klaviyo_events(orders_df, profiles, charges_df)
    google_ads_df = build_google_ads()
    gorgias_df = build_gorgias_tickets(orders_df, profiles)

    write_outputs(
        {
            "shopify_products.csv": products_df,
            "shopify_orders.csv": orders_df,
            "shopify_customers.csv": customers_df,
            "shopify_order_items.csv": order_items_df,
            "recharge_subscriptions.csv": subs_df,
            "recharge_subscription_orders.csv": charges_df,
            "ga4_reporting_purchase_events.csv": ga4_orders_df,
            "ga4_reporting_purchase_items.csv": ga4_items_df,
            "klaviyo_events.csv": klaviyo_df,
            "google_ads_campaign_performance.csv": google_ads_df,
            "gorgias_tickets.csv": gorgias_df,
        }
    )


if __name__ == "__main__":
    main()
