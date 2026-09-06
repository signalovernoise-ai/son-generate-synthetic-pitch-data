"""Raw source generator for Sunna Supplements.

Builds the Shopify commerce spine (products -> orders -> customers -> order_items) plus Skio
(subscriptions + billing attempts), GA4, Klaviyo, Google Ads, Meta Ads, TikTok Ads and Gorgias.

Four things drive this generator and differ from previous companies:

1. **Islamic-calendar seasonality that migrates.** Ramadan is the peak trading window and starts
   ~11 days earlier each year, so the peak month walks backwards (Mar 2025 -> Feb/Mar 2026 ->
   Feb 2027). Seasonality is baked into MONTHLY_ORDER_TARGETS; the generator pins order counts
   to it and does not apply a second multiplier.

2. **Ramadan bulk buying suppresses near-term repeat.** Ramadan months shift the supply-tier
   mix hard toward 3- and 6-month supplies, and a customer who buys a 3- or 6-month supply is
   genuinely not in the market again for 3-5 months. That is modelled as a real eligibility
   delay in the repeat pool, not as a label — which is why Ramadan cohorts legitimately look
   like the worst retainers on an order-recency curve.

3. **Multi-month supplies are variants, not baskets.** A "3 Months" supply is ONE order line at
   a list-price discount, so lines per order stay near 1 and AOV is driven by the supply-tier
   mix. Baskets are calibrated to the NET price the customer pays, never to compare_at_price.

4. **Free delivery, no threshold.** Shipping is 0.00 on every order, so there is no basket
   bunching and no GA4-vs-Shopify shipping revenue gap. The revenue quirks here come instead
   from the Navidium shipping-protection SKU, genuine GBP 0.00 gift lines, and Intelligems
   price tests serving two prices for one variant with no discount recorded.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from synthetic_pitch_data.company.sunna.config import (
    BULK_REPEAT_SUPPRESSION_MONTHS,
    BUSINESS,
    CANCEL_LAG_RATE,
    DUPLICATE_ORDER_NAME_RATE,
    EMAIL_DRIFT_RATE,
    GA4_RENEWAL_CAPTURE,
    GA4_WEB_LOSS,
    GIFT_LINE_RATE,
    GOOGLE_ADS_START,
    GORGIAS_NO_CUSTOMER_RATE,
    GORGIAS_NO_ORDER_RATE,
    INTELLIGEMS_TESTED_SKUS,
    INTELLIGEMS_TEST_RATE,
    KLAVIYO_START,
    KLAVIYO_US_PROFILE_RATE,
    META_ADS_START,
    MIN_NEW_SHARE,
    MONTHLY_AOV,
    MONTHLY_ORDER_TARGETS,
    MONTHLY_REFUND_RATE,
    NAVIDIUM_ATTACH_RATE,
    PRODUCTS,
    RAMADAN_MONTHS,
    RENEWAL_SURVIVAL,
    RENEWAL_SURVIVAL_TAIL,
    ROW_SCALE,
    SEED,
    SHIPPING_STANDARD,
    SOURCE_WINDOW_END,
    SOURCE_WINDOW_START,
    TEST_ORDER_RATE,
    TIKTOK_ADS_START,
    TRACKING_BREAKS,
    UNATTRIBUTED_BASELINE,
    VAT_RATE,
    WELCOME_DISCOUNT,
    WELCOME_TAKE_RATE,
    adhoc_repeat_share,
    sub_take_rate,
    supply_tier_weights,
)
from synthetic_pitch_data.paths import ensure_workspace_dirs
from synthetic_pitch_data.raw_common import print_source_summary, write_source_csv


# Name pool for a UK brand whose audience is predominantly British Muslim, mixed with the
# general UK population the brand also sells to.
FIRST_NAMES = [
    "Aisha", "Fatima", "Maryam", "Zainab", "Khadija", "Amina", "Sumaya", "Hafsa", "Ayesha",
    "Muhammad", "Ahmed", "Yusuf", "Ibrahim", "Bilal", "Hamza", "Omar", "Zaid", "Imran",
    "Sarah", "Emily", "Sophie", "Olivia", "Hannah", "Grace", "James", "Daniel", "Adam", "Ben",
]

LAST_NAMES = [
    "Khan", "Ali", "Hussain", "Ahmed", "Patel", "Rahman", "Iqbal", "Malik", "Begum",
    "Choudhury", "Sheikh", "Mahmood", "Aslam", "Yusuf", "Farah", "Osman",
    "Smith", "Jones", "Taylor", "Brown", "Wilson", "Evans", "Roberts", "Clarke",
]

# (city, county, county_code) — weighted to the UK's largest Muslim populations, which is
# where this brand's demand actually sits.
CITIES = [
    ("London", "Greater London", "LND"),
    ("Birmingham", "West Midlands", "WMD"),
    ("Manchester", "Greater Manchester", "MAN"),
    ("Bradford", "West Yorkshire", "WYK"),
    ("Leicester", "Leicestershire", "LEC"),
    ("Blackburn", "Lancashire", "LAN"),
    ("Luton", "Bedfordshire", "BDF"),
    ("Leeds", "West Yorkshire", "WYK"),
    ("Glasgow", "Glasgow City", "GLG"),
    ("Cardiff", "Cardiff", "CRF"),
]
CITY_WEIGHTS = [0.30, 0.14, 0.11, 0.08, 0.07, 0.05, 0.05, 0.07, 0.07, 0.06]

POSTCODE_AREAS = ["E", "SE", "SW", "N", "NW", "B", "M", "BD", "LE", "BB", "LU", "LS", "G", "CF"]

EMAIL_DOMAINS = ["gmail.com", "outlook.com", "hotmail.co.uk", "yahoo.co.uk", "icloud.com"]

# Acquisition channels. Paid social is unusually dominant here (~170 active GB Meta ads and
# 1,034 GB TikTok ads in 2026 YTD), so it sits above the benchmark band.
# channel_group, source, medium, source_platform
CH_PAID_SOCIAL_META = ("Paid Social", "facebook", "paid_social", "Meta")
CH_PAID_SOCIAL_TIKTOK = ("Paid Social", "tiktok", "paid_social", "TikTok")
CH_PAID_SEARCH = ("Paid Search", "google", "cpc", "Google Ads")
CH_DIRECT = ("Direct", "(direct)", "(none)", "Direct")
CH_ORGANIC = ("Organic Search", "google", "organic", "Google")
CH_EMAIL = ("Email", "klaviyo", "email", "Klaviyo")
CH_REFERRAL = ("Referral", "skio-referrals", "referral", "Skio")
CH_AFFILIATE = ("Affiliate", "creator", "affiliate", "Creator")

CHANNELS = [
    CH_PAID_SOCIAL_META, CH_PAID_SOCIAL_TIKTOK, CH_PAID_SEARCH, CH_DIRECT,
    CH_ORGANIC, CH_EMAIL, CH_REFERRAL, CH_AFFILIATE,
]
# Normalised over attributed channels only; the ~8% unattributed floor is applied separately
# in GA4 so the baseline is not double-counted (see references/channel-mix-benchmarks.md).
CHANNEL_WEIGHTS = [0.23, 0.13, 0.15, 0.12, 0.11, 0.11, 0.04, 0.03]

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge"]
DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.78, 0.16, 0.06]

MONTH_KEYS = [str(m) for m in pd.period_range(SOURCE_WINDOW_START, SOURCE_WINDOW_END, freq="M")]
MONTH_INDEX = {m: i for i, m in enumerate(MONTH_KEYS)}
WINDOW_START_TS = pd.Timestamp(SOURCE_WINDOW_START, tz="UTC")
WINDOW_END_TS = pd.Timestamp(SOURCE_WINDOW_END + " 23:59:59", tz="UTC")
KLAVIYO_START_TS = pd.Timestamp(KLAVIYO_START, tz="UTC")
NOW = pd.Timestamp("2026-08-13", tz="UTC")

# Product weights within the supplement range. Collagen is the hero and carries the brand.
PRODUCT_KEY_WEIGHTS = {
    "COLLAGEN": 0.26, "SACHETS": 0.09, "MARINE": 0.11, "ELECTRO": 0.08, "CREATINE": 0.07,
    "D3K2": 0.07, "MAGNESIUM": 0.06, "TURMERIC": 0.05, "OMEGA3": 0.05, "IMMUNITY": 0.05,
    "IRON": 0.04, "BLACKSEED": 0.04, "BSOSOFT": 0.03, "MANGOLASSI": 0.02, "PROBIOTIC": 0.03,
    "COLLAGEN750": 0.02, "COLLAGENSHAKER": 0.01, "COLLAGEN250": 0.01, "VITC": 0.01,
}

# Composition of a new-customer order: mostly a single supply variant, with a small share of
# bundle-led and accessory-led orders.
NEW_ORDER_COMPOSITION = [("supply", 0.84), ("bundle", 0.09), ("accessory", 0.07)]
ADHOC_ORDER_COMPOSITION = [("supply", 0.88), ("bundle", 0.06), ("accessory", 0.06)]


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


def renewal_timestamp(rng, month_key: str, anchor: pd.Timestamp, gap_months: int, not_before: pd.Timestamp) -> pd.Timestamp:
    """Place a recurring charge on its scheduled anniversary, not at a random point in the
    month.

    Skio bills a fixed number of days after the previous charge, so inter-order gaps cluster
    tightly around 30 / 91 / 183 days. Scattering renewals uniformly across the target calendar
    month would widen those gaps enough to smear the cohort-retention curve once retention is
    bucketed by elapsed days rather than by calendar month.
    """
    target = anchor + pd.Timedelta(days=30.44 * gap_months) + pd.Timedelta(
        seconds=int(rng.integers(-2 * 86400, 2 * 86400))
    )
    lo = max(month_start(month_key), not_before)
    hi = month_end(month_key) + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)
    if lo >= hi:
        return hi
    return min(max(target, lo), hi)


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


def skio_uuid(prefix: str, serial: int) -> str:
    """Skio ids are UUID strings, not integers — preserved deliberately, because a warehouse
    that types subscription ids as BIGINT breaks on a Skio migration."""
    h = hashlib.sha1(f"{prefix}:{serial}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# --------------------------------------------------------------------------- products
def _product_index() -> dict[str, dict]:
    out = {}
    product_ids: dict[str, int] = {}
    for idx, spec in enumerate(PRODUCTS, start=1):
        if spec.product_key not in product_ids:
            product_ids[spec.product_key] = 7300000 + len(product_ids) + 1
        out[spec.sku] = {
            "product_id": f"gid://shopify/Product/{product_ids[spec.product_key]}",
            "variant_id": f"gid://shopify/ProductVariant/{9400000 + idx}",
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
                "vendor": "Sunna Supplements",
                "product_type": spec.product_type,
                "status": status,
                "published_at": to_iso(launch_ts if launch_ts < NOW else NOW),
                "created_at": to_iso(launch_ts),
                "updated_at": to_iso(NOW),
                "variant_id": meta["variant_id"],
                "sku": spec.sku,
                "barcode": f"{5070002272000 + meta['idx']}",
                "option_1": spec.option_1,
                "option_2": pd.NA,
                "option_3": pd.NA,
                "price": round(spec.base_price, 2),
                "compare_at_price": round(spec.compare_at_price, 2),
                # Supplement COGS runs ~26% of net; shipping protection has no product cost.
                "cost": 0.0 if spec.role == "shipping_protection" else round(spec.base_price * 0.26, 2),
                "inventory_quantity": int(900 + meta["idx"] * 53),
                "requires_shipping": spec.role not in ("shipping_protection",),
            }
        )
    return pd.DataFrame(rows)


def _as_item(spec) -> dict:
    meta = PRODUCT_IDX[spec.sku]
    return {
        "product_id": meta["product_id"],
        "variant_id": meta["variant_id"],
        "sku": spec.sku,
        "title": spec.title,
        "option_1": spec.option_1,
        "product_key": spec.product_key,
        "product_type": spec.product_type,
        "role": spec.role,
        "base_price": spec.base_price,
        "compare_at_price": spec.compare_at_price,
        "subscription_eligible": spec.subscription_eligible,
        "sub_discount": spec.sub_discount,
        "supply_months": spec.supply_months,
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


_SUPPLY_CACHE: dict[str, dict] = {}


def supply_pool(month_key: str) -> dict:
    """Supply variants available this month, grouped by tier, with product weights."""
    if month_key not in _SUPPLY_CACHE:
        pools = roles_for_month(month_key)
        by_tier = {}
        for months in (1, 3, 6):
            items = pools.get(f"supply_{months}m", [])
            weights = [PRODUCT_KEY_WEIGHTS.get(i["product_key"], 0.02) for i in items]
            by_tier[months] = (items, np.array(weights, dtype=float))
        _SUPPLY_CACHE[month_key] = by_tier
    return _SUPPLY_CACHE[month_key]


def pick_supply(rng, month_key: str, tier_weights: dict[int, float]) -> dict:
    by_tier = supply_pool(month_key)
    tiers = [t for t in (1, 3, 6) if by_tier[t][0]]
    probs = np.array([tier_weights[t] for t in tiers], dtype=float)
    tier = tiers[int(rng.choice(len(tiers), p=probs / probs.sum()))]
    items, weights = by_tier[tier]
    return items[int(rng.choice(len(items), p=weights / weights.sum()))]


def pick_role(rng, month_key: str, role: str) -> dict | None:
    pool = roles_for_month(month_key).get(role)
    if not pool:
        return None
    return pool[int(rng.integers(0, len(pool)))]


def navidium_tier(rng, month_key: str, order_net: float) -> dict | None:
    """Navidium prices shipping protection as a ladder against order value."""
    pool = roles_for_month(month_key).get("shipping_protection")
    if not pool:
        return None
    ordered = sorted(pool, key=lambda p: p["base_price"])
    idx = min(len(ordered) - 1, max(0, int(order_net // 8)))
    return ordered[idx]


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
    ramadan_acquired: bool
    email_drift: bool
    legacy: bool


def create_customer_profile(rng, serial, created_at, promo_acquired, ramadan_acquired=False, legacy=False) -> CustomerProfile:
    first_name = FIRST_NAMES[int(rng.integers(0, len(FIRST_NAMES)))]
    last_name = LAST_NAMES[int(rng.integers(0, len(LAST_NAMES)))]
    cw = np.array(CITY_WEIGHTS, dtype=float)
    city, county, county_code = CITIES[int(rng.choice(len(CITIES), p=cw / cw.sum()))]
    probs = np.array(CHANNEL_WEIGHTS, dtype=float)
    ch = CHANNELS[int(rng.choice(len(CHANNELS), p=probs / probs.sum()))]
    accepts = rng.choice(["true", "false", "blank"], p=[0.71, 0.23, 0.06])
    return CustomerProfile(
        customer_id=str(8200000 + serial),
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
        ramadan_acquired=ramadan_acquired,
        email_drift=bool(rng.random() < EMAIL_DRIFT_RATE),
        legacy=legacy,
    )


def build_shopify_customers(profiles: list[CustomerProfile], rng) -> pd.DataFrame:
    rows = []
    for p in profiles:
        display_email = drift_email(p.canonical_email, rng) if p.email_drift else p.canonical_email
        tags = []
        if p.legacy:
            tags.append("legacy")
        if p.ramadan_acquired:
            tags.append("ramadan-cohort")
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
                "tags": ",".join(tags),
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

    __slots__ = ("kind", "customer", "ts", "lines", "sub_group", "is_test", "welcome", "supply_months")

    def __init__(self, kind, customer, ts, lines, sub_group=None, is_test=False, welcome=False, supply_months=0):
        self.kind = kind            # new | renewal | adhoc
        self.customer = customer
        self.ts = ts
        self.lines = lines          # list of (item, qty, unit_price, list_price)
        self.sub_group = sub_group
        self.is_test = is_test
        self.welcome = welcome
        self.supply_months = supply_months


def build_core_sources():
    """Acquisition-led order engine with a Skio subscription overlay.

    Each month's fixed order target is composed of (a) Skio renewals from the surviving active
    base whose cycle falls due this month, (b) one-time repeat purchases from past buyers who
    are actually back in the market, and (c) new customers. Renewals beyond the month's
    capacity skip to the next cycle rather than disappearing, which is what a subscription
    portal does.

    Repeat eligibility is the Ramadan mechanism: a customer who bought a 3- or 6-month supply
    is not eligible for a one-time repeat for 3 or 5 months. Ramadan skews the supply mix hard
    toward those tiers, so Ramadan cohorts genuinely go quiet afterwards.
    """
    rng = np.random.default_rng(SEED)
    profiles: dict[str, CustomerProfile] = {}
    profile_list: list[CustomerProfile] = []
    active_subs: dict[int, dict] = {}
    all_subs: list[dict] = []

    # Every past buyer sits in `repeat_pool` once; `next_eligible` gates when they are
    # actually back in the market. A 3- or 6-month supply keeps them out for 3 or 5 months,
    # which is the mechanism behind the Ramadan retention artefact.
    repeat_pool: list[str] = []
    in_repeat_pool: set[str] = set()
    next_eligible: dict[str, int] = {}

    order_rows: list[dict] = []
    line_rows: list[dict] = []
    charge_rows: list[dict] = []
    name_pool: list[str] = []
    cs = os_ = li = gid = chg = 1

    def new_profile(ts, promo_acquired=False, ramadan_acquired=False, legacy=False):
        nonlocal cs
        p = create_customer_profile(rng, cs, ts, promo_acquired, ramadan_acquired, legacy=legacy)
        cs += 1
        profiles[p.customer_id] = p
        profile_list.append(p)
        return p

    def schedule_repeat(customer_id, midx, supply_months):
        """A customer is back in the market only when their supply actually runs out."""
        delay = BULK_REPEAT_SUPPRESSION_MONTHS.get(supply_months, 0) + 1
        next_eligible[customer_id] = midx + delay
        if customer_id not in in_repeat_pool:
            in_repeat_pool.add(customer_id)
            repeat_pool.append(customer_id)

    def open_subscription(customer, ts, midx, item, unit_price, bf_cohort, month_key):
        nonlocal gid
        interval = item["supply_months"] if item["supply_months"] in (1, 3, 6) else 1
        group = {
            "group_id": gid,
            "customer_id": customer.customer_id,
            "created_at": ts,
            "interval": interval,
            "next_idx": midx + interval,
            "cycle": 0,
            "bf_cohort": bf_cohort,
            "status": "ACTIVE",
            "cancelled_at": None,
            "cancel_reason": "",
            "paused_at": None,
            "last_charge_ts": ts,
            "last_charge_idx": midx,
            "skip_count": 0,
            "swap_count": 0,
            "lines": [{"item": item, "qty": 1, "unit_price": unit_price}],
        }
        gid += 1
        active_subs[group["group_id"]] = group
        all_subs.append(group)
        return group

    def cancel_subscription(group):
        """Cancellation is recorded when the customer acts in the portal, which routinely lags
        the last successful billing attempt (modelled data issue). Churned subscribers stay
        eligible for later one-time repeat purchases."""
        lag_days = int(rng.integers(1, 20))
        if rng.random() < CANCEL_LAG_RATE:
            lag_days = int(rng.integers(38, 95))
        cancelled = group["last_charge_ts"] + pd.Timedelta(days=lag_days)
        group["status"] = "CANCELLED"
        group["cancelled_at"] = min(cancelled, WINDOW_END_TS)
        group["cancel_reason"] = str(
            weighted_choice(
                rng,
                ["TOO_MUCH_PRODUCT", "TOO_EXPENSIVE", "FOUND_ALTERNATIVE", "QUALITY", "OTHER", ""],
                [0.30, 0.24, 0.14, 0.08, 0.16, 0.08],
                1,
            )[0]
        )
        active_subs.pop(group["group_id"], None)
        schedule_repeat(group["customer_id"], MONTH_INDEX.get(str(group["last_charge_ts"])[:7], 0), 1)

    # --- seed the pre-window population ------------------------------------------------
    # The brand incorporated 2022-08 and did ~£4.2m in CY2024, so a substantial customer base
    # already exists when the window opens. Left-censoring it is a selected data issue.
    t0_orders = int(round(MONTHLY_ORDER_TARGETS[MONTH_KEYS[0]] * ROW_SCALE))
    legacy_subs = int(round(0.95 * t0_orders))
    legacy_buyers = int(round(2.80 * t0_orders))
    seed_pools = roles_for_month(MONTH_KEYS[0])
    seed_items = seed_pools["supply_1m"] + seed_pools["supply_3m"]
    for _ in range(legacy_subs):
        age_months = int(rng.integers(1, 15))
        created = WINDOW_START_TS - pd.Timedelta(days=int(age_months * 30 + rng.integers(0, 28)))
        customer = new_profile(created, promo_acquired=False, legacy=True)
        item = seed_items[int(rng.integers(0, len(seed_items)))]
        unit = round(item["base_price"] * (1 - item["sub_discount"]), 2)
        group = open_subscription(customer, created, -age_months, item, unit, False, MONTH_KEYS[0])
        interval = group["interval"]
        group["cycle"] = min(5, max(1, age_months // interval))
        group["next_idx"] = int(rng.integers(0, interval))
        # Anchor the schedule one full cycle before the next due charge so the first in-window
        # renewal lands on a realistic gap rather than an artificially short one.
        group["last_charge_idx"] = group["next_idx"] - interval
        group["last_charge_ts"] = WINDOW_START_TS + pd.Timedelta(
            days=30.44 * group["last_charge_idx"] + int(rng.integers(0, 25))
        )
    for _ in range(legacy_buyers):
        created = WINDOW_START_TS - pd.Timedelta(days=int(rng.integers(30, 720)))
        customer = new_profile(created, promo_acquired=False, legacy=True)
        in_repeat_pool.add(customer.customer_id)
        repeat_pool.append(customer.customer_id)
        next_eligible[customer.customer_id] = 0

    # --- monthly loop -------------------------------------------------------------------
    for midx, month_key in enumerate(MONTH_KEYS):
        target_orders = int(round(MONTHLY_ORDER_TARGETS[month_key] * ROW_SCALE))
        target_revenue = target_orders * MONTHLY_AOV[month_key]
        tier_weights = supply_tier_weights(month_key)
        take_rate = sub_take_rate(month_key)
        adhoc_share = adhoc_repeat_share(month_key)
        is_black_friday = month_key.endswith("-11")
        is_ramadan = month_key in RAMADAN_MONTHS
        pools = roles_for_month(month_key)
        intents: list[Intent] = []

        # 1. Renewals due this month, after applying per-cycle survival.
        due = [g for g in active_subs.values() if g["next_idx"] == midx]
        survivors = []
        for group in due:
            cycle = group["cycle"] + 1
            surv = RENEWAL_SURVIVAL.get(cycle, RENEWAL_SURVIVAL_TAIL)
            if group["bf_cohort"]:
                surv *= 0.93
            if rng.random() < surv:
                survivors.append(group)
            else:
                cancel_subscription(group)

        adhoc_target = int(round(adhoc_share * target_orders))
        min_new = max(1, int(round(MIN_NEW_SHARE * target_orders)))
        max_renewals = max(0, target_orders - min_new - adhoc_target)
        if len(survivors) > max_renewals:
            keep_idx = set(int(i) for i in rng.choice(len(survivors), size=max_renewals, replace=False))
            for i, group in enumerate(survivors):
                if i not in keep_idx:
                    group["next_idx"] = midx + 1      # skip this cycle (Skio skip/delay)
                    group["skip_count"] += 1
            survivors = [g for i, g in enumerate(survivors) if i in keep_idx]

        for group in survivors:
            customer = profiles[group["customer_id"]]
            ts = renewal_timestamp(
                rng, month_key, group["last_charge_ts"],
                midx - group["last_charge_idx"], customer.created_at,
            )
            lines = [(ln["item"], ln["qty"], ln["unit_price"], ln["item"]["base_price"]) for ln in group["lines"]]
            intents.append(Intent("renewal", customer, ts, lines, sub_group=group))
            group["cycle"] += 1
            group["next_idx"] = midx + group["interval"]
            group["last_charge_ts"] = ts
            group["last_charge_idx"] = midx

        # 2. One-time repeat purchases from past buyers who are back in the market.
        adhoc_count = min(adhoc_target, max(0, target_orders - len(survivors) - min_new))
        picked_adhoc = 0
        if repeat_pool and adhoc_count > 0:
            # Draw until the month's ad-hoc quota is filled, rejecting customers whose supply
            # has not run out yet. Drawn in batches because the ineligible share swings with
            # how bulk-heavy the preceding months were (Ramadan pushes it up sharply).
            attempts = 0
            max_attempts = adhoc_count * 12 + 500
            while picked_adhoc < adhoc_count and attempts < max_attempts:
                batch = rng.choice(len(repeat_pool), size=min(len(repeat_pool), (adhoc_count - picked_adhoc) * 2 + 16), replace=True)
                attempts += len(batch)
                for i in batch:
                    if picked_adhoc >= adhoc_count:
                        break
                    cid = repeat_pool[int(i)]
                    if next_eligible.get(cid, 0) > midx:
                        continue                 # supply has not run out yet
                    customer = profiles[cid]
                    ts = random_timestamp_after(rng, month_key, customer.created_at)
                    comp = str(weighted_choice(rng, [c for c, _ in ADHOC_ORDER_COMPOSITION],
                                               [w for _, w in ADHOC_ORDER_COMPOSITION], 1)[0])
                    if comp == "supply":
                        item = pick_supply(rng, month_key, tier_weights)
                    else:
                        item = pick_role(rng, month_key, comp) or pick_supply(rng, month_key, tier_weights)
                    intents.append(Intent("adhoc", customer, ts, [(item, 1, item["base_price"], item["base_price"])],
                                          supply_months=item["supply_months"]))
                    schedule_repeat(cid, midx, item["supply_months"])
                    picked_adhoc += 1
        adhoc_count = picked_adhoc

        # 3. New customers fill the remainder; a growing share start a Skio subscription.
        new_count = max(0, target_orders - len(survivors) - adhoc_count)
        for _ in range(new_count):
            ts = random_timestamp_in_month(rng, month_key)
            subscribes = bool(rng.random() < take_rate)
            comp = str(weighted_choice(rng, [c for c, _ in NEW_ORDER_COMPOSITION],
                                       [w for _, w in NEW_ORDER_COMPOSITION], 1)[0])
            if subscribes or comp == "supply":
                item = pick_supply(rng, month_key, tier_weights)
            else:
                item = pick_role(rng, month_key, comp) or pick_supply(rng, month_key, tier_weights)
            customer = new_profile(ts, promo_acquired=is_black_friday, ramadan_acquired=is_ramadan)
            welcome = bool(rng.random() < WELCOME_TAKE_RATE)
            if subscribes and item["subscription_eligible"]:
                unit = round(item["base_price"] * (1 - item["sub_discount"]), 2)
                group = open_subscription(customer, ts, midx, item, unit, is_black_friday, month_key)
                intents.append(Intent("new", customer, ts, [(item, 1, unit, item["base_price"])],
                                      sub_group=group, supply_months=item["supply_months"]))
            else:
                unit = round(item["base_price"] * (1 - WELCOME_DISCOUNT), 2) if welcome else item["base_price"]
                intents.append(Intent("new", customer, ts, [(item, 1, unit, item["base_price"])],
                                      welcome=welcome, supply_months=item["supply_months"]))
                schedule_repeat(customer.customer_id, midx, item["supply_months"])

        # 4. Test / internal orders (data issue) — flagged, then zeroed out below.
        for intent in intents:
            if rng.random() < TEST_ORDER_RATE:
                intent.is_test = True

        # 5. Intelligems price tests: the same variant sells at two prices on the same day with
        #    no discount recorded, because the price itself is what the test varies.
        for intent in intents:
            if intent.kind == "renewal" or intent.is_test:
                continue
            new_lines = []
            for item, qty, unit, listp in intent.lines:
                if item["sku"] in INTELLIGEMS_TESTED_SKUS and rng.random() < INTELLIGEMS_TEST_RATE:
                    factor = 0.90 if rng.random() < 0.6 else 1.10
                    tested = round(item["base_price"] * factor, 2)
                    new_lines.append((item, qty, tested, tested))   # list == sell, so no discount
                else:
                    new_lines.append((item, qty, unit, listp))
            intent.lines = new_lines

        # 6. Genuine GBP 0.00 gift and lead-magnet lines (data issue). Never the only line.
        gift_pool = pools.get("gift") or []
        if gift_pool:
            for intent in intents:
                if intent.kind == "renewal" or intent.is_test:
                    continue
                if rng.random() < GIFT_LINE_RATE:
                    gift = gift_pool[int(rng.integers(0, len(gift_pool)))]
                    intent.lines.append((gift, 1, 0.00, 0.00))

        # 7. AOV calibration. Close the gap between the base baskets and the month's revenue
        #    target: a shortfall buys accessory add-on lines, an overshoot applies a promo
        #    discount to non-renewal orders. Renewals are contractual and are never re-priced.
        live = [i for i in intents if not i.is_test]
        base_total = sum(qty * price for i in live for _, qty, price, _ in i.lines)
        flexible = [i for i in live if i.kind != "renewal"]
        addon_pool = pools.get("accessory", [])
        addon_mean = float(np.mean([p["base_price"] for p in addon_pool])) if addon_pool else 8.0
        # Navidium attaches at a known rate and adds a known expected value per order.
        navidium_ev = NAVIDIUM_ATTACH_RATE * 3.20
        gap = target_revenue - base_total - navidium_ev * len(live)
        promo_rate = 0.0
        addon_p = 0.0
        if flexible:
            if gap > 0:
                addon_p = min(0.90, gap / (len(flexible) * addon_mean))
            else:
                flex_total = sum(qty * price for i in flexible for _, qty, price, _ in i.lines)
                promo_rate = min(0.35, -gap / flex_total) if flex_total else 0.0

        for intent in flexible:
            if addon_p and addon_pool and rng.random() < addon_p:
                extra = addon_pool[int(rng.integers(0, len(addon_pool)))]
                intent.lines.append((extra, 1, extra["base_price"], extra["base_price"]))

        # 8. Materialise orders and line items.
        for intent in intents:
            customer = intent.customer
            is_renewal = intent.kind == "renewal"
            is_first_sub = intent.kind == "new" and intent.sub_group is not None
            discount_rate = 0.0 if (is_renewal or intent.is_test) else promo_rate
            order_id = str(6100000000 + os_)
            order_name = f"#SUN{200000 + os_}"
            if name_pool and rng.random() < DUPLICATE_ORDER_NAME_RATE:
                order_name = name_pool[int(rng.integers(0, len(name_pool)))]
            else:
                name_pool.append(order_name)

            # Navidium shipping protection is an insurance upsell that lands in order_items
            # like merchandise (data issue). Priced against the order value, so add it last.
            working = list(intent.lines)
            pre_net = sum(qty * price for _, qty, price, _ in working)
            if not intent.is_test and not is_renewal and rng.random() < NAVIDIUM_ATTACH_RATE:
                nvd = navidium_tier(rng, month_key, pre_net)
                if nvd is not None:
                    working.append((nvd, 1, nvd["base_price"], nvd["base_price"]))

            gross = 0.0
            net = 0.0
            lines: list[dict] = []
            for item, qty, unit_price, list_price in working:
                protect = item["role"] == "shipping_protection"
                sell = unit_price if protect else round(unit_price * (1.0 - discount_rate), 2)
                if intent.is_test:
                    sell = 0.0
                gross += list_price * qty
                net += sell * qty
                subscribed = is_renewal or (is_first_sub and item["subscription_eligible"] and item["role"].startswith("supply"))
                interval = intent.sub_group["interval"] if (subscribed and intent.sub_group) else None
                lines.append(
                    {
                        "order_id": order_id,
                        "line_item_id": f"gid://shopify/LineItem/{9700000000 + li}",
                        "admin_graphql_api_id": f"gid://shopify/LineItem/{9700000000 + li}",
                        "product_id": item["product_id"],
                        "variant_id": item["variant_id"],
                        "sku": item["sku"],
                        "title": item["title"],
                        "variant_title": item["option_1"],
                        "vendor": "Sunna Supplements",
                        "product_type": item["product_type"],
                        "quantity": int(qty),
                        "price": round(list_price, 2),
                        "discounted_price": sell,
                        "total_discount": round(max(0.0, (list_price - sell) * qty), 2),
                        "taxable": True,
                        "requires_shipping": not protect,
                        "fulfillment_status": "fulfilled",
                        "selling_plan_name": (
                            f"Subscribe & Save - every {interval} month{'s' if interval and interval > 1 else ''}"
                            if subscribed else pd.NA
                        ),
                        "selling_plan_id": (
                            f"sp_{hashlib.sha1(f'{item['sku']}:{interval}'.encode()).hexdigest()[:10]}"
                            if subscribed else pd.NA
                        ),
                    }
                )
                li += 1

            total_price = round(net, 2)
            total_line_items_price = round(gross, 2)
            total_discounts = round(max(0.0, total_line_items_price - total_price), 2)
            total_tax = round(total_price * VAT_RATE / (1 + VAT_RATE), 2)
            shipping = SHIPPING_STANDARD          # blanket free delivery, no threshold

            refund_rate = MONTHLY_REFUND_RATE[month_key] + (0.005 if customer.promo_acquired else 0.0)
            refund_status, refunded_amount, financial_status = "none", 0.0, "paid"
            if not intent.is_test and rng.random() < refund_rate:
                if rng.random() < 0.58:
                    refund_status, refunded_amount, financial_status = "full", total_price, "refunded"
                else:
                    refund_status, financial_status = "partial", "partially_refunded"
                    refunded_amount = 0.0 if rng.random() < 0.14 else round(total_price * rng.uniform(0.2, 0.7), 2)

            order_rows.append(
                {
                    "id": order_id,
                    "admin_graphql_api_id": f"gid://shopify/Order/{6100000000 + os_}",
                    "order_number": 200000 + os_,
                    "name": order_name,
                    "customer_id": customer.customer_id,
                    "email": (
                        f"qa.test.{os_}@sunnasupplements.com" if intent.is_test else customer.canonical_email
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
                    "total_weight": int(320 * sum(int(ln["quantity"]) for ln in lines)),
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
                sub_id = skio_uuid("sub", group["group_id"])
                charge_rows.append(
                    {
                        "id": skio_uuid("chg", chg),
                        "subscription_id": sub_id,
                        "platform_customer_id": skio_uuid("cust", group["group_id"]),
                        "shopify_customer_id": customer.customer_id,
                        "shopify_order_id": order_id,
                        "origin": "RECURRING" if is_renewal else "CHECKOUT",
                        "status": "SUCCEEDED",
                        "error_code": "",
                        "scheduled_at": to_iso(intent.ts.normalize()),
                        "processed_at": to_iso(intent.ts),
                        "created_at": to_iso(intent.ts),
                        "updated_at": to_iso(intent.ts + pd.Timedelta(hours=int(rng.integers(1, 30)))),
                        "subtotal_price": total_price,
                        "total_discounts": total_discounts,
                        "total_tax": total_tax,
                        "shipping_price": round(shipping, 2),
                        "total_price": round(total_price + shipping, 2),
                        "currency": "GBP",
                        "attempt_number": 1,
                        "next_retry_at": "",
                        "tags": "",
                    }
                )
                chg += 1
                # Dunning: a small share of recurring charges fail first and are retried. A
                # FAILED attempt never created a Shopify order, so its FK is legitimately blank.
                if is_renewal and rng.random() < 0.014 and intent.ts - pd.Timedelta(days=2) >= WINDOW_START_TS:
                    charge_rows.append(
                        {
                            "id": skio_uuid("chg", chg),
                            "subscription_id": sub_id,
                            "platform_customer_id": skio_uuid("cust", group["group_id"]),
                            "shopify_customer_id": customer.customer_id,
                            "shopify_order_id": "",
                            "origin": "RECURRING",
                            "status": "FAILED",
                            "error_code": str(
                                weighted_choice(
                                    rng,
                                    ["CARD_DECLINED", "EXPIRED_PAYMENT_METHOD", "INSUFFICIENT_FUNDS", "PROCESSING_ERROR"],
                                    [0.46, 0.24, 0.22, 0.08],
                                    1,
                                )[0]
                            ),
                            "scheduled_at": to_iso((intent.ts - pd.Timedelta(days=2)).normalize()),
                            "processed_at": to_iso(intent.ts - pd.Timedelta(days=2)),
                            "created_at": to_iso(intent.ts - pd.Timedelta(days=2)),
                            "updated_at": to_iso(intent.ts - pd.Timedelta(days=1)),
                            "subtotal_price": total_price,
                            "total_discounts": total_discounts,
                            "total_tax": total_tax,
                            "shipping_price": round(shipping, 2),
                            "total_price": round(total_price + shipping, 2),
                            "currency": "GBP",
                            "attempt_number": int(rng.integers(2, 4)),
                            "next_retry_at": to_iso(intent.ts.normalize()),
                            "tags": "dunning",
                        }
                    )
                    chg += 1
            os_ += 1

    customers_df = build_shopify_customers(profile_list, np.random.default_rng(SEED + 3))
    orders_df = pd.DataFrame(order_rows).sort_values("created_at").reset_index(drop=True)
    order_items_df = pd.DataFrame(line_rows).reset_index(drop=True)
    charges_df = pd.DataFrame(charge_rows).sort_values("created_at").reset_index(drop=True)
    subs_df = build_skio_subscriptions(all_subs, profiles)
    return customers_df, orders_df, order_items_df, charges_df, subs_df, profiles, all_subs


def build_skio_subscriptions(all_subs: list[dict], profiles: dict) -> pd.DataFrame:
    """One row per subscribed line. Skio ids are UUID strings and enums are UPPER_SNAKE."""
    rows = []
    for group in all_subs:
        customer = profiles[group["customer_id"]]
        interval = group["interval"]
        for line_no, line in enumerate(group["lines"]):
            item = line["item"]
            created = group["created_at"]
            next_billing = ""
            if group["status"] == "ACTIVE":
                nxt = group["last_charge_ts"] + pd.Timedelta(days=30.44 * interval)
                next_billing = to_iso(nxt)
            rows.append(
                {
                    "id": skio_uuid("sub", group["group_id"]) if line_no == 0 else skio_uuid(f"sub{line_no}", group["group_id"]),
                    "platform_customer_id": skio_uuid("cust", group["group_id"]),
                    "shopify_customer_id": customer.customer_id,
                    "shopify_subscription_contract_id": f"gid://shopify/SubscriptionContract/{5500000 + group['group_id']}",
                    "status": group["status"],
                    "created_at": to_iso(created),
                    "updated_at": to_iso(group["cancelled_at"] or group["last_charge_ts"]),
                    "cancelled_at": to_iso(group["cancelled_at"]) if group["cancelled_at"] is not None else "",
                    "cancellation_reason": group["cancel_reason"] if group["cancelled_at"] is not None else "",
                    "paused_at": "",
                    "next_billing_date": next_billing,
                    "selling_plan_id": f"sp_{hashlib.sha1(f'{item['sku']}:{interval}'.encode()).hexdigest()[:10]}",
                    "selling_plan_name": f"Subscribe & Save - every {interval} month{'s' if interval > 1 else ''}",
                    "selling_plan_discount_percentage": int(round(item["sub_discount"] * 100)),
                    "billing_interval_unit": "MONTH",
                    "billing_interval_count": interval,
                    "delivery_interval_unit": "MONTH",
                    "delivery_interval_count": interval,
                    "quantity": int(line["qty"]),
                    "price": round(float(line["unit_price"]), 2),
                    "presentment_currency": "GBP",
                    "product_title": item["title"],
                    "variant_title": item["option_1"],
                    "sku": item["sku"],
                    "shopify_product_id": item["product_id"],
                    "shopify_variant_id": item["variant_id"],
                    "is_prepaid": False,
                    "swap_count": int(group["swap_count"]),
                    "skip_count": int(group["skip_count"]),
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

    Skio recurring billing attempts are processed server-side with no browser session, so they
    almost never fire a web purchase event; the few that do carry Direct / (not set), never a
    paid channel. Shipping is free and 0.00, so purchaseRevenue matches Shopify total_price and
    there is no shipping-driven revenue definition mismatch for this brand.
    """
    rng = np.random.default_rng(SEED + 11)
    renewal_order_ids = set(
        charges.loc[(charges["origin"] == "RECURRING") & (charges["shopify_order_id"] != ""), "shopify_order_id"]
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
        device = str(weighted_choice(rng, DEVICES, DEVICE_WEIGHTS, 1)[0])
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
                "deviceCategory": device,
                "platformDeviceCategory": device,
                "country": "United Kingdom",
                "region": order.billing_address_province,
                "city": order.billing_address_city,
                "streamId": "8814402271",
                "platform": "web",
                "user_id": order.customer_id if rng.random() < 0.86 else pd.NA,
                "itemPromotionId": pd.NA,
                "itemPromotionName": pd.NA,
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
                    "itemBrand": "Sunna Supplements",
                    "itemVariant": item["variant_title"],
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
    """One Klaviyo account serves both the UK and US Shopify stores, so a slice of the profile
    base legitimately never joins to the UK commerce spine (selected data issue)."""
    rng = np.random.default_rng(SEED + 23)
    renewal_order_ids = set(
        charges.loc[(charges["origin"] == "RECURRING") & (charges["shopify_order_id"] != ""), "shopify_order_id"]
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
        ("Replenishment Reminder", "flow_replenishment"),
        ("Abandoned Checkout", "flow_abandoned"),
        ("Win-back", "flow_winback"),
    ]
    campaigns = [
        ("Ramadan Prep", "cmp_ramadanprep"),
        ("Eid Mubarak", "cmp_eid"),
        ("New Drop - Creatine", "cmp_creatine"),
        ("Immunity Season", "cmp_immunity"),
        ("Black Friday", "cmp_blackfriday"),
        ("New Year Reset", "cmp_newyear"),
    ]

    def emit(profile_id, email, phone_ok, base_ts, metric, channel, flow=None, campaign=None,
             value=None, attributed_channel=None):
        nonlocal eid
        if base_ts < KLAVIYO_START_TS or base_ts > WINDOW_END_TS:
            return
        rows.append(
            {
                "event_id": f"01M{eid:012d}",
                "timestamp": to_iso(base_ts),
                "metric_id": metric_ids.get(metric, "MISC"),
                "metric_name": metric,
                "profile_id": profile_id,
                "email": email,
                "phone_number": f"+447{700000000 + (eid % 99999999)}" if (channel == "sms" and phone_ok) else pd.NA,
                "channel": channel,
                "$message": f"msg_{eid % 9000}",
                "campaign_id": campaign[1] if campaign else pd.NA,
                "campaign_name": campaign[0] if campaign else pd.NA,
                "$flow": flow[1] if flow else pd.NA,
                "$flow_message_id": f"{flow[1]}_m1" if flow else pd.NA,
                "flow_name": flow[0] if flow else pd.NA,
                "subject": "Time to restock?" if channel == "email" else pd.NA,
                "$variation": pd.NA,
                "url": "https://sunnasupplements.com/" if metric in ("Clicked Email", "Clicked SMS") else pd.NA,
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

    def emit_profile(profile, *args, **kwargs):
        email = drift_email(profile.canonical_email, rng) if profile.email_drift else profile.canonical_email
        emit(f"prof_{profile.customer_id}", email, True, *args, **kwargs)

    for order in recent.itertuples(index=False):
        if order.source_name == "internal":
            continue
        profile = profiles[str(order.customer_id)]
        if profile.accepts_marketing != "true" and rng.random() < 0.74:
            continue
        order_ts = pd.Timestamp(order.created_at)
        is_renewal = str(order.id) in renewal_order_ids
        flow = flows[2] if is_renewal else flows[1]
        base = order_ts + pd.Timedelta(hours=int(rng.integers(1, 40)))
        emit_profile(profile, base, "Received Email", "email", flow=flow)
        if rng.random() < 0.47:
            emit_profile(profile, base + pd.Timedelta(hours=int(rng.integers(1, 20))), "Opened Email", "email", flow=flow)
            if rng.random() < 0.26:
                emit_profile(profile, base + pd.Timedelta(hours=int(rng.integers(2, 30))), "Clicked Email", "email", flow=flow)
        if rng.random() < 0.21:
            sbase = order_ts + pd.Timedelta(days=int(rng.integers(22, 65)))
            emit_profile(profile, sbase, "Received SMS", "sms", flow=flows[2])
            if rng.random() < 0.14:
                emit_profile(profile, sbase + pd.Timedelta(hours=int(rng.integers(1, 8))), "Clicked SMS", "sms", flow=flows[2])
        # Klaviyo tracks renewals server-side but must not credit them as click-driven.
        if not is_renewal and rng.random() < 0.14:
            emit_profile(
                profile, order_ts, "Placed Order", "email", flow=flow,
                value=float(order.total_price),
                attributed_channel="email" if rng.random() < 0.70 else "sms",
            )

    marketable = [p for p in profiles.values() if p.accepts_marketing == "true"]
    for month_key in MONTH_KEYS:
        m_start = month_start(month_key)
        if m_start < KLAVIYO_START_TS or m_start > WINDOW_END_TS:
            continue
        if month_key in RAMADAN_MONTHS:
            campaign = campaigns[0] if month_key.endswith("-01") or month_key.endswith("-02") else campaigns[1]
        elif month_key.endswith("-11"):
            campaign = campaigns[4]
        elif month_key.endswith("-01"):
            campaign = campaigns[5]
        else:
            campaign = campaigns[int(rng.integers(2, 4))]
        sample = rng.choice(len(marketable), size=min(len(marketable), 14000), replace=False)
        send_ts = m_start + pd.Timedelta(days=int(rng.integers(2, 26)), hours=int(rng.integers(8, 18)))
        for i in sample:
            profile = marketable[int(i)]
            emit_profile(profile, send_ts, "Received Email", "email", campaign=campaign)
            if rng.random() < 0.29:
                emit_profile(profile, send_ts + pd.Timedelta(hours=int(rng.integers(1, 30))), "Opened Email", "email", campaign=campaign)
                if rng.random() < 0.15:
                    emit_profile(profile, send_ts + pd.Timedelta(hours=int(rng.integers(2, 40))), "Clicked Email", "email", campaign=campaign)
            elif rng.random() < 0.02:
                emit_profile(profile, send_ts + pd.Timedelta(minutes=int(rng.integers(1, 40))), "Unsubscribed", "email", campaign=campaign)

    # US-store profiles: same Klaviyo account, different Shopify store, so these emails never
    # resolve to a UK customer. Extra CRM rows only — never orphan commerce rows.
    uk_profiles = len({r["profile_id"] for r in rows})
    us_count = int(round(uk_profiles * KLAVIYO_US_PROFILE_RATE / (1 - KLAVIYO_US_PROFILE_RATE)))
    us_campaign = ("US Launch - Halal Collagen", "cmp_uslaunch")
    us_start = max(KLAVIYO_START_TS, pd.Timestamp("2025-11-01", tz="UTC"))
    for n in range(us_count):
        first = FIRST_NAMES[int(rng.integers(0, len(FIRST_NAMES)))]
        last = LAST_NAMES[int(rng.integers(0, len(LAST_NAMES)))]
        email = f"{first}.{last}.us{n}".lower() + "@" + EMAIL_DOMAINS[int(rng.integers(0, len(EMAIL_DOMAINS)))]
        pid = f"prof_us_{n}"
        span = (WINDOW_END_TS - us_start).days
        ts = us_start + pd.Timedelta(days=int(rng.integers(0, max(1, span))), hours=int(rng.integers(0, 24)))
        emit(pid, email, False, ts, "Received Email", "email", campaign=us_campaign)
        if rng.random() < 0.30:
            emit(pid, email, False, ts + pd.Timedelta(hours=int(rng.integers(1, 30))), "Opened Email", "email", campaign=us_campaign)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Google Ads
def build_google_ads():
    rng = np.random.default_rng(SEED + 41)
    start = pd.Timestamp(GOOGLE_ADS_START, tz="UTC")
    end = pd.Timestamp(SOURCE_WINDOW_END, tz="UTC")
    account_id, account_name = "1106473499", "Sunna Supplements"
    campaigns = [
        ("Brand - Sunna Supplements", "SEARCH", "TARGET_SPEND", 70, None),
        ("Non-Brand - Halal Collagen", "SEARCH", "MAXIMIZE_CONVERSIONS", 380, None),
        ("Non-Brand - Halal Supplements", "SEARCH", "MAXIMIZE_CONVERSIONS", 240, None),
        ("Non-Brand - Black Seed Oil", "SEARCH", "MAXIMIZE_CONVERSIONS", 130, "2025-07-12"),
        ("Non-Brand - Creatine Halal", "SEARCH", "MAXIMIZE_CONVERSIONS", 120, "2025-10-31"),
        ("Competitor", "SEARCH", "MAXIMIZE_CONVERSIONS", 80, None),
        ("Shopping - Collagen", "SHOPPING", "MAXIMIZE_CONVERSION_VALUE", 300, None),
        ("Shopping - Vitamins & Minerals", "SHOPPING", "MAXIMIZE_CONVERSION_VALUE", 170, None),
        ("Performance Max - Prospecting", "PERFORMANCE_MAX", "MAXIMIZE_CONVERSION_VALUE", 520, None),
        ("Performance Max - Retention", "PERFORMANCE_MAX", "MAXIMIZE_CONVERSION_VALUE", 180, None),
        ("Demand Gen - Halal Wellness", "DEMAND_GEN", "MAXIMIZE_CONVERSIONS", 140, None),
        ("Ramadan - Seasonal Push", "SEARCH", "MAXIMIZE_CONVERSION_VALUE", 160, None),
    ]
    rows = []
    for c_i, (cname, channel_type, bidding, base_spend, launch) in enumerate(campaigns):
        campaign_id = f"{2240000000 + c_i}"
        c_start = max(start, pd.Timestamp(launch, tz="UTC")) if launch else start
        for day in pd.date_range(c_start.normalize(), end.normalize(), freq="D", tz="UTC"):
            month_key = day.strftime("%Y-%m")
            progress = (day - start).days / max(1, (end - start).days)
            season = 1.0
            if month_key in RAMADAN_MONTHS:
                season = 1.55
            elif day.month == 11:
                season = 1.40
            elif day.month == 1:
                season = 1.20
            elif day.month in (7, 8):
                season = 0.82
            if cname.startswith("Ramadan"):
                if month_key not in RAMADAN_MONTHS:
                    continue
                season *= 1.6
            spend = round(base_spend * (0.55 + 1.05 * progress) * season * float(rng.uniform(0.82, 1.18)), 2)
            if spend < 1:
                continue
            cost_micros = int(round(spend * 1_000_000))
            impressions = int(spend / float(rng.uniform(0.006, 0.020)))
            ctr_base = rng.uniform(0.06, 0.13) if cname.startswith("Brand") else rng.uniform(0.008, 0.030)
            clicks = max(1, int(impressions * float(ctr_base)))
            conversions = round(clicks * float(rng.uniform(0.035, 0.095)), 2)
            conv_value = round(conversions * float(rng.uniform(36.0, 52.0)), 2)
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
                    "metrics.all_conversions": round(conversions * 1.16, 2),
                    "metrics.all_conversions_value": round(conv_value * 1.16, 2),
                    "metrics.ctr": round(clicks / impressions, 4) if impressions else 0.0,
                    "metrics.average_cpc": int(round(cost_micros / clicks)) if clicks else 0,
                    "metrics.average_cpm": int(round(cost_micros / impressions * 1000)) if impressions else 0,
                    "metrics.search_impression_share": (
                        round(float(rng.uniform(0.20, 0.68)), 4) if channel_type == "SEARCH" else pd.NA
                    ),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Meta Ads
META_CAMPAIGNS = [
    ("Prospecting - Halal Collagen", "OUTCOME_SALES", 0.30),
    ("Prospecting - Broad", "OUTCOME_SALES", 0.20),
    ("Creator Whitelisting", "OUTCOME_SALES", 0.16),
    ("Retargeting - Site Visitors", "OUTCOME_SALES", 0.14),
    ("Ramadan - Seasonal", "OUTCOME_SALES", 0.12),
    ("Awareness - Brand", "OUTCOME_AWARENESS", 0.08),
]
META_ADSETS = ["Advantage+ Broad", "Interest - Halal Wellness", "Lookalike 1% Purchasers", "Retarget 30d"]
CREATOR_HANDLES = ["Sadiyah", "Amina", "Yusuf", "Nadia", "Bilal", "Zara"]
META_ANGLES = [
    "Hair Skin Nails", "One Scoop A Day", "3 Free Gifts", "Halal Certified", "Founder Story",
    "Before & After", "Third Party Tested", "100k Customers", "Morning Coffee Routine",
]


def build_meta_ads():
    """Ad-level daily insights plus a creative dimension. Creative churn is high: ads run in
    short flights, which is what an always-on paid-social programme actually looks like."""
    rng = np.random.default_rng(SEED + 47)
    start = pd.Timestamp(META_ADS_START, tz="UTC")
    end = pd.Timestamp(SOURCE_WINDOW_END, tz="UTC")
    total_days = (end - start).days
    account_id, account_name = "act_418862094471", "Sunna Supplements"

    ads = []
    for a in range(110):
        c_i = int(weighted_choice(rng, list(range(len(META_CAMPAIGNS))), [w for _, _, w in META_CAMPAIGNS], 1)[0])
        cname, objective, _ = META_CAMPAIGNS[c_i]
        adset = META_ADSETS[int(rng.integers(0, len(META_ADSETS)))]
        angle = META_ANGLES[int(rng.integers(0, len(META_ANGLES)))]
        is_creator = cname.startswith("Creator")
        creator = CREATOR_HANDLES[int(rng.integers(0, len(CREATOR_HANDLES)))] if is_creator else None
        flight_start = start + pd.Timedelta(days=int(rng.integers(0, max(1, total_days - 40))))
        flight_len = int(rng.integers(35, 220))
        ads.append({
            "ad_id": f"{6238500000000 + a}",
            "campaign_i": c_i,
            "campaign_id": f"{6238400000000 + c_i}",
            "campaign_name": cname,
            "objective": objective,
            "adset_id": f"{6238450000000 + a}",
            "adset_name": adset,
            "ad_name": (f"{creator} x Sunna - {angle}" if creator else f"{angle} - v{a % 7 + 1}"),
            "creator": creator,
            "angle": angle,
            "start": flight_start,
            "end": min(end, flight_start + pd.Timedelta(days=flight_len)),
            "base_spend": float(rng.uniform(28, 260)),
            "quality": float(rng.uniform(0.7, 1.35)),
        })

    rows, creatives = [], []
    for ad in ads:
        for day in pd.date_range(ad["start"].normalize(), ad["end"].normalize(), freq="D", tz="UTC"):
            month_key = day.strftime("%Y-%m")
            progress = (day - start).days / max(1, total_days)
            season = 1.0
            if month_key in RAMADAN_MONTHS:
                season = 1.60
            elif day.month == 11:
                season = 1.45
            elif day.month == 1:
                season = 1.22
            elif day.month in (7, 8):
                season = 0.80
            if ad["campaign_name"].startswith("Ramadan") and month_key not in RAMADAN_MONTHS:
                continue
            spend = round(ad["base_spend"] * (0.55 + 1.10 * progress) * season * float(rng.uniform(0.75, 1.25)), 2)
            if spend < 1:
                continue
            cpm = float(rng.uniform(4.5, 13.5)) / season ** 0.5
            impressions = int(spend / cpm * 1000)
            reach = int(impressions / float(rng.uniform(1.15, 1.9)))
            ctr = float(rng.uniform(0.006, 0.022)) * ad["quality"]
            clicks = max(1, int(impressions * ctr))
            link_clicks = int(clicks * float(rng.uniform(0.55, 0.85)))
            purchases = max(0, int(round(link_clicks * float(rng.uniform(0.012, 0.045)) * ad["quality"])))
            purchase_value = round(purchases * float(rng.uniform(36.0, 54.0)), 2)
            atc = int(link_clicks * float(rng.uniform(0.05, 0.14)))
            rows.append(
                {
                    "date_start": day.strftime("%Y-%m-%d"),
                    "date_stop": day.strftime("%Y-%m-%d"),
                    "account_id": account_id,
                    "account_name": account_name,
                    "account_currency": "GBP",
                    "campaign_id": ad["campaign_id"],
                    "campaign_name": ad["campaign_name"],
                    "objective": ad["objective"],
                    "adset_id": ad["adset_id"],
                    "adset_name": ad["adset_name"],
                    "ad_id": ad["ad_id"],
                    "ad_name": ad["ad_name"],
                    "impressions": impressions,
                    "reach": reach,
                    "frequency": round(impressions / reach, 4) if reach else 0.0,
                    "clicks": clicks,
                    "inline_link_clicks": link_clicks,
                    "spend": spend,
                    "cpc": round(spend / clicks, 4) if clicks else 0.0,
                    "cpm": round(spend / impressions * 1000, 4) if impressions else 0.0,
                    "ctr": round(clicks / impressions, 6) if impressions else 0.0,
                    "actions": (
                        f'[{{"action_type":"add_to_cart","value":"{atc}"}},'
                        f'{{"action_type":"omni_purchase","value":"{purchases}"}},'
                        f'{{"action_type":"offsite_conversion.fb_pixel_purchase","value":"{purchases}"}}]'
                    ),
                    "action_values": (
                        f'[{{"action_type":"omni_purchase","value":"{purchase_value}"}},'
                        f'{{"action_type":"offsite_conversion.fb_pixel_purchase","value":"{purchase_value}"}}]'
                    ),
                    "purchase_roas": (
                        f'[{{"action_type":"omni_purchase","value":"{round(purchase_value / spend, 4)}"}}]'
                        if spend else "[]"
                    ),
                }
            )
        creatives.append(
            {
                "ad_id": ad["ad_id"],
                "creative_id": f"{2380000000000 + int(ad['ad_id']) % 100000}",
                "creative_name": ad["ad_name"],
                "object_type": "VIDEO" if ad["creator"] or rng.random() < 0.72 else "SHARE",
                "call_to_action_type": "SHOP_NOW",
                "title": "Halal Collagen, Third-Party Tested",
                "body": f"{ad['angle']} - trusted by 100,000+ customers.",
                "thumbnail_url": f"https://scontent.xx.fbcdn.net/v/t45.{ad['ad_id']}_thumb.jpg",
                "instagram_permalink_url": (
                    f"https://www.instagram.com/p/{hashlib.sha1(ad['ad_id'].encode()).hexdigest()[:11]}/"
                ),
                "effective_object_story_id": f"61567778153379_{ad['ad_id']}",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(creatives)


# --------------------------------------------------------------------------- TikTok Ads
TIKTOK_CAMPAIGNS = [
    ("Prospecting - Halal Collagen", "CONVERSIONS", 0.32),
    ("Spark Ads - Creator", "CONVERSIONS", 0.24),
    ("Prospecting - Broad", "CONVERSIONS", 0.18),
    ("Retargeting", "CONVERSIONS", 0.12),
    ("Ramadan - Seasonal", "PRODUCT_SALES", 0.09),
    ("Video Views - Awareness", "VIDEO_VIEWS", 0.05),
]
TIKTOK_ADGROUPS = ["Broad 18-34", "Broad 25-44 F", "Interest - Fitness", "Retarget VV75", "Lookalike Purchasers"]


def build_tiktok_ads():
    """TikTok runs very high creative churn — 1,034 GB ads in 2026 YTD — so ads are modelled as
    many short flights. `conversion` is the optimisation event; `complete_payment` is the
    purchase event and is the one that reconciles to commerce."""
    rng = np.random.default_rng(SEED + 53)
    start = pd.Timestamp(TIKTOK_ADS_START, tz="UTC")
    end = pd.Timestamp(SOURCE_WINDOW_END, tz="UTC")
    total_days = (end - start).days
    advertiser_id, advertiser_name = "7291840255013748738", "SUNNA SUPPLEMENTS LTD"

    ads = []
    for a in range(200):
        c_i = int(weighted_choice(rng, list(range(len(TIKTOK_CAMPAIGNS))), [w for _, _, w in TIKTOK_CAMPAIGNS], 1)[0])
        cname, objective, _ = TIKTOK_CAMPAIGNS[c_i]
        is_spark = cname.startswith("Spark")
        flight_start = start + pd.Timedelta(days=int(rng.integers(0, max(1, total_days - 20))))
        flight_len = int(rng.integers(12, 110))
        ads.append({
            "ad_id": f"{1791250000000000 + a}",
            "campaign_id": f"{1791240000000000 + c_i}",
            "campaign_name": cname,
            "objective_type": objective,
            "adgroup_id": f"{1791245000000000 + a}",
            "adgroup_name": TIKTOK_ADGROUPS[int(rng.integers(0, len(TIKTOK_ADGROUPS)))],
            "ad_name": f"{'Spark' if is_spark else 'IAA'}_{META_ANGLES[a % len(META_ANGLES)].replace(' ', '')}_{a}",
            "identity_type": "AUTH_CODE" if is_spark else ("TT_USER" if rng.random() < 0.25 else "CUSTOMIZED_USER"),
            "placement_type": "PLACEMENT_TYPE_AUTOMATIC" if rng.random() < 0.8 else "PLACEMENT_TYPE_NORMAL",
            "start": flight_start,
            "end": min(end, flight_start + pd.Timedelta(days=flight_len)),
            "base_spend": float(rng.uniform(14, 150)),
            "quality": float(rng.uniform(0.65, 1.4)),
        })

    rows = []
    for ad in ads:
        for day in pd.date_range(ad["start"].normalize(), ad["end"].normalize(), freq="D", tz="UTC"):
            month_key = day.strftime("%Y-%m")
            progress = (day - start).days / max(1, total_days)
            season = 1.0
            if month_key in RAMADAN_MONTHS:
                season = 1.65
            elif day.month == 11:
                season = 1.40
            elif day.month == 1:
                season = 1.25
            elif day.month in (7, 8):
                season = 0.80
            if ad["campaign_name"].startswith("Ramadan") and month_key not in RAMADAN_MONTHS:
                continue
            # TikTok scaled hard through the window; earlier months are much smaller.
            spend = round(ad["base_spend"] * (0.30 + 1.60 * progress) * season * float(rng.uniform(0.7, 1.3)), 2)
            if spend < 1:
                continue
            cpm = float(rng.uniform(2.2, 7.5))
            impressions = int(spend / cpm * 1000)
            reach = int(impressions / float(rng.uniform(1.1, 1.7)))
            ctr = float(rng.uniform(0.004, 0.014)) * ad["quality"]
            clicks = max(1, int(impressions * ctr))
            conversion = max(0, int(round(clicks * float(rng.uniform(0.03, 0.10)) * ad["quality"])))
            complete_payment = max(0, int(round(conversion * float(rng.uniform(0.30, 0.55)))))
            purchase_value = round(complete_payment * float(rng.uniform(34.0, 50.0)), 2)
            plays = int(impressions * float(rng.uniform(0.72, 0.95)))
            p25 = int(plays * float(rng.uniform(0.34, 0.52)))
            p50 = int(p25 * float(rng.uniform(0.50, 0.72)))
            p75 = int(p50 * float(rng.uniform(0.55, 0.78)))
            p100 = int(p75 * float(rng.uniform(0.55, 0.85)))
            rows.append(
                {
                    "stat_time_day": day.strftime("%Y-%m-%d"),
                    "advertiser_id": advertiser_id,
                    "advertiser_name": advertiser_name,
                    "currency": "GBP",
                    "campaign_id": ad["campaign_id"],
                    "campaign_name": ad["campaign_name"],
                    "objective_type": ad["objective_type"],
                    "adgroup_id": ad["adgroup_id"],
                    "adgroup_name": ad["adgroup_name"],
                    "placement_type": ad["placement_type"],
                    "ad_id": ad["ad_id"],
                    "ad_name": ad["ad_name"],
                    "identity_type": ad["identity_type"],
                    "impressions": impressions,
                    "reach": reach,
                    "frequency": round(impressions / reach, 4) if reach else 0.0,
                    "clicks": clicks,
                    "spend": spend,
                    "cpc": round(spend / clicks, 4) if clicks else 0.0,
                    "cpm": round(spend / impressions * 1000, 4) if impressions else 0.0,
                    "ctr": round(clicks / impressions * 100, 4) if impressions else 0.0,
                    "conversion": conversion,
                    "cost_per_conversion": round(spend / conversion, 4) if conversion else 0.0,
                    "conversion_rate": round(conversion / clicks * 100, 4) if clicks else 0.0,
                    "complete_payment": complete_payment,
                    "complete_payment_roas": round(purchase_value / spend, 4) if spend else 0.0,
                    "total_purchase_value": purchase_value,
                    "video_play_actions": plays,
                    "video_watched_2s": int(plays * float(rng.uniform(0.40, 0.62))),
                    "video_watched_6s": int(plays * float(rng.uniform(0.18, 0.34))),
                    "video_views_p25": p25,
                    "video_views_p50": p50,
                    "video_views_p75": p75,
                    "video_views_p100": p100,
                    "average_video_play": round(float(rng.uniform(1.8, 6.5)), 2),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Gorgias
def build_gorgias_tickets(orders, profiles):
    """Order and customer linkage is agent-applied, so it is sparse by design.

    NOTE: Gorgias is a user-directed ASSUMPTION for this client — no helpdesk signature was
    detectable on the live site. See sunna.yaml source_systems.confirmed[Gorgias].
    """
    rng = np.random.default_rng(SEED + 59)
    subjects = [
        ("Where is my order?", "shipping", "email"),
        ("How do I pause my subscription?", "subscription", "chat"),
        ("Cancel my subscription", "cancellation", "email"),
        ("Is the collagen halal certified?", "product_question", "chat"),
        ("Can I change my delivery frequency?", "subscription", "chat"),
        ("Refund request - 30 day guarantee", "refund", "email"),
        ("Which supplement should I take with iron?", "product_question", "email"),
        ("Damaged pouch on arrival", "product_fault", "instagram"),
        ("Did not receive my free gifts", "promotion", "chat"),
        ("Ramadan delivery cut-off?", "shipping", "email"),
    ]
    sample = orders[orders["source_name"] != "internal"].sample(frac=0.025, random_state=SEED).reset_index(drop=True)
    rows = []
    for idx, order in enumerate(sample.itertuples(index=False), start=1):
        profile = profiles[str(order.customer_id)]
        subject, tag, default_channel = subjects[int(rng.integers(0, len(subjects)))]
        created = pd.Timestamp(order.created_at) + pd.Timedelta(days=int(rng.integers(1, 21)))
        created = min(created, WINDOW_END_TS)
        closed = created + pd.Timedelta(hours=int(rng.integers(2, 120)))
        status = "open" if rng.random() < 0.15 else "closed"
        channel = default_channel if rng.random() < 0.8 else str(
            weighted_choice(rng, ["email", "chat", "sms", "instagram", "contact-form"], [0.4, 0.28, 0.1, 0.12, 0.1], 1)[0]
        )
        has_order = rng.random() >= GORGIAS_NO_ORDER_RATE
        has_customer = rng.random() >= GORGIAS_NO_CUSTOMER_RATE
        tags = f"{tag},vip" if rng.random() < 0.06 else tag
        if rng.random() < 0.05:
            tags = tags.upper()
        rows.append(
            {
                "id": str(4300000 + idx),
                "created_datetime": to_iso(created),
                "updated_datetime": to_iso(closed),
                "opened_datetime": to_iso(created),
                "closed_datetime": to_iso(closed) if status == "closed" else "",
                "status": status,
                "priority": str(weighted_choice(rng, ["normal", "high", "urgent"], [0.81, 0.16, 0.03], 1)[0]),
                "channel": channel,
                "via": "chat" if channel == "chat" else ("api" if channel in ("facebook", "instagram") else "email"),
                "subject": subject,
                "excerpt": f"Customer contacted us about {tag.replace('_', ' ')}.",
                "from_email": profile.canonical_email if has_customer else f"anon{idx}@mail-relay.example",
                "customer_id": str(7700000 + idx),
                "shopify_customer_id": order.customer_id if has_customer else "",
                "shopify_order_id": order.id if has_order else "",
                "assignee_user_id": str(660000 + int(rng.integers(1, 12))),
                "team_id": str(9900 + int(rng.integers(1, 3))),
                "tags": tags,
                "satisfaction_score": int(rng.integers(3, 6)) if (status == "closed" and rng.random() < 0.26) else "",
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
    meta_ads_df, meta_creatives_df = build_meta_ads()
    tiktok_ads_df = build_tiktok_ads()
    gorgias_df = build_gorgias_tickets(orders_df, profiles)

    write_outputs(
        {
            "shopify_products.csv": products_df,
            "shopify_orders.csv": orders_df,
            "shopify_customers.csv": customers_df,
            "shopify_order_items.csv": order_items_df,
            "skio_subscriptions.csv": subs_df,
            "skio_subscription_orders.csv": charges_df,
            "ga4_reporting_purchase_events.csv": ga4_orders_df,
            "ga4_reporting_purchase_items.csv": ga4_items_df,
            "klaviyo_events.csv": klaviyo_df,
            "google_ads_campaign_performance.csv": google_ads_df,
            "meta_ads_insights.csv": meta_ads_df,
            "meta_ad_creatives.csv": meta_creatives_df,
            "tiktok_ads_insights.csv": tiktok_ads_df,
            "gorgias_tickets.csv": gorgias_df,
        }
    )


if __name__ == "__main__":
    main()
