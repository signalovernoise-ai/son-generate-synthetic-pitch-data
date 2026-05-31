"""Raw source generator for Luminary Vitamins.

Builds the Shopify commerce spine (products -> orders -> customers -> order_items)
plus GA4, Klaviyo (email/SMS), Meta Ads, Google Ads (future-only), and Zendesk.

Calibration note: Luminary products carry no list-price discount (compare_at == price);
subscribe & save (15%) and a first-order welcome offer (10%) are applied explicitly at the
line. AOV is therefore controlled by a per-month feedback controller that steers
mean(total_price) to the approved monthly AOV target, so the metric-trajectory check passes
without the gross/compare_at miscalibration seen on other companies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from synthetic_pitch_data.company.luminary.config import (
    BUSINESS,
    GOOGLE_ADS_START,
    KLAVIYO_START,
    META_START,
    MONTHLY_AOV,
    MONTHLY_NEW_ORDER_SHARE,
    MONTHLY_ORDER_TARGETS,
    MONTHLY_REFUND_RATE,
    MONTHLY_SUBSCRIPTION_SHARE,
    PRODUCTS,
    ROW_SCALE,
    SEED,
    SOURCE_WINDOW_END,
    SOURCE_WINDOW_START,
    SUBSCRIPTION_DISCOUNT,
    WELCOME_DISCOUNT,
    WELCOME_USE_RATE,
)
from synthetic_pitch_data.paths import ensure_workspace_dirs
from synthetic_pitch_data.raw_common import print_source_summary, write_source_csv


FIRST_NAMES = [
    "Emily", "Jessica", "Ashley", "Sarah", "Olivia", "Emma", "Madison", "Hannah",
    "Michael", "David", "Chris", "James", "Daniel", "Ryan", "Matthew", "Andrew",
    "Sophia", "Ava", "Mia", "Rachel",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
]

# (city, state, state_code)
CITIES = [
    ("New York", "New York", "NY"),
    ("Los Angeles", "California", "CA"),
    ("Chicago", "Illinois", "IL"),
    ("Houston", "Texas", "TX"),
    ("Phoenix", "Arizona", "AZ"),
    ("Austin", "Texas", "TX"),
    ("Seattle", "Washington", "WA"),
    ("Denver", "Colorado", "CO"),
    ("Atlanta", "Georgia", "GA"),
    ("Boston", "Massachusetts", "MA"),
]

EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "icloud.com", "hotmail.com"]

# Acquisition channels for a paid-social-led US DTC fertility brand. Paid Search is
# added only from GOOGLE_ADS_START (keyword block lifted), so it is excluded for customers
# acquired earlier.
# channel_group, source, medium, source_platform
CH_PAID_SOCIAL = ("Paid Social", "facebook", "paid_social", "Facebook")
CH_PAID_SEARCH = ("Paid Search", "google", "paid_search", "Google Ads")
CH_EMAIL = ("Email", "klaviyo", "email", "Klaviyo")
CH_ORGANIC = ("Organic Search", "google", "organic", "Google")
CH_DIRECT = ("Direct", "(direct)", "(none)", "Direct")
CH_REFERRAL = ("Referral", "referral", "referral", "Referral")

CHANNELS_PRE = [CH_PAID_SOCIAL, CH_EMAIL, CH_ORGANIC, CH_DIRECT, CH_REFERRAL]
CHANNEL_WEIGHTS_PRE = [0.44, 0.08, 0.18, 0.18, 0.12]
CHANNELS_POST = [CH_PAID_SOCIAL, CH_PAID_SEARCH, CH_EMAIL, CH_ORGANIC, CH_DIRECT, CH_REFERRAL]
CHANNEL_WEIGHTS_POST = [0.38, 0.12, 0.07, 0.16, 0.18, 0.09]

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge"]
DEVICES = ["mobile", "desktop", "tablet"]

MONTH_KEYS = [str(m) for m in pd.period_range(SOURCE_WINDOW_START, SOURCE_WINDOW_END, freq="M")]
GOOGLE_START_TS = pd.Timestamp(GOOGLE_ADS_START, tz="UTC")
KLAVIYO_START_TS = pd.Timestamp(KLAVIYO_START, tz="UTC")
WINDOW_END_TS = pd.Timestamp(SOURCE_WINDOW_END + " 23:59:59", tz="UTC")
NOW = pd.Timestamp("2026-05-31", tz="UTC")

# Retention-led subscription engine knobs (tuned so orders/buyer ~2.5 and the
# fertility-realistic retention curve lands ~M1 0.35 / M3 0.22 / M6 0.12 / M12 0.05).
SUB_CONVERSION = 0.42      # share of new customers who start a subscription
ADHOC_REPEAT_SHARE = 0.10  # share of monthly orders that are one-time repeats
MIN_NEW_SHARE = 0.24       # floor share of monthly orders that are new acquisitions


@dataclass
class CustomerProfile:
    customer_id: str
    canonical_email: str
    first_name: str
    last_name: str
    created_at: pd.Timestamp
    updated_at: pd.Timestamp
    city: str
    state: str
    state_code: str
    zip_code: str
    accepts_marketing: str | None
    acquisition_channel: str
    source: str
    medium: str
    source_platform: str
    segment: str
    gender: str            # male | female
    primary_category: str  # male | female | unisex
    promo_acquired: bool
    email_drift: bool
    guest_fragmentation: bool


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


def zip_code(rng) -> str:
    return f"{int(rng.integers(10000, 99999))}"


def slugify_title(value: str) -> str:
    slug = value.lower().replace("&", "and").replace("+", "plus").replace(",", "")
    slug = slug.replace("'", "").replace(".", "").replace("(", "").replace(")", "")
    return "-".join(slug.split())


# --------------------------------------------------------------------------- products
def _product_index() -> dict[str, dict]:
    out = {}
    for idx, spec in enumerate(PRODUCTS, start=1):
        out[spec.sku] = {
            "product_id": f"gid://shopify/Product/{300000 + idx}",
            "variant_id": f"gid://shopify/ProductVariant/{500000 + idx}",
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
                "vendor": "Luminary Vitamins",
                "product_type": spec.category,
                "status": status,
                "published_at": to_iso(launch_ts if launch_ts < NOW else NOW),
                "created_at": to_iso(launch_ts),
                "updated_at": to_iso(NOW),
                "variant_id": meta["variant_id"],
                "sku": spec.sku,
                "barcode": f"{860000000000 + meta['idx']}",
                "option_1": "Default Title",
                "option_2": pd.NA,
                "option_3": pd.NA,
                "price": round(spec.base_price, 2),
                "compare_at_price": round(spec.compare_at_price, 2),
                "cost": round(spec.base_price * 0.28, 2),
                "inventory_quantity": int(800 + meta["idx"] * 23),
            }
        )
    return pd.DataFrame(rows)


def active_products_for_date(ts: pd.Timestamp) -> list[dict]:
    out = []
    for spec in PRODUCTS:
        launch_ts = pd.Timestamp(spec.launch_date, tz="UTC")
        retire_ts = pd.Timestamp(spec.retire_date, tz="UTC") if spec.retire_date else None
        if ts < launch_ts:
            continue
        if retire_ts is not None and ts > retire_ts:
            continue
        meta = PRODUCT_IDX[spec.sku]
        out.append(
            {
                "product_id": meta["product_id"],
                "variant_id": meta["variant_id"],
                "sku": spec.sku,
                "title": spec.title,
                "category": spec.category,
                "base_price": spec.base_price,
                "subscription_eligible": spec.subscription_eligible,
            }
        )
    return out


def _pick_product(rng, ts, gender: str, allow_bundle: bool) -> dict:
    pool = active_products_for_date(ts)
    weights = []
    for p in pool:
        cat = p["category"]
        if cat == "bundle":
            w = 0.6 if allow_bundle else 0.0
        elif cat == "unisex":
            w = 0.5
        elif cat == gender:
            w = 1.0
        else:  # opposite gender
            w = 0.12
        weights.append(w)
    if sum(weights) <= 0:
        weights = [1.0 if p["category"] != "bundle" else 0.0 for p in pool]
    probs = np.array(weights, dtype=float)
    probs = probs / probs.sum()
    return pool[int(rng.choice(len(pool), p=probs))]


# --------------------------------------------------------------------------- customers
def create_customer_profile(rng, serial, created_at, promo_acquired) -> CustomerProfile:
    first_name = FIRST_NAMES[int(rng.integers(0, len(FIRST_NAMES)))]
    last_name = LAST_NAMES[int(rng.integers(0, len(LAST_NAMES)))]
    city, state, state_code = CITIES[int(rng.integers(0, len(CITIES)))]
    email = make_email(first_name, last_name, serial, rng)
    if created_at >= GOOGLE_START_TS:
        ch = CHANNELS_POST[int(rng.choice(len(CHANNELS_POST), p=np.array(CHANNEL_WEIGHTS_POST) / sum(CHANNEL_WEIGHTS_POST)))]
    else:
        ch = CHANNELS_PRE[int(rng.choice(len(CHANNELS_PRE), p=np.array(CHANNEL_WEIGHTS_PRE) / sum(CHANNEL_WEIGHTS_PRE)))]
    segment = rng.choice(["one_time", "repeat", "loyal"], p=[0.50, 0.34, 0.16])
    # Female fertility/prenatal line is the larger market; male (sperm) is the hero SKU.
    gender = rng.choice(["female", "male"], p=[0.62, 0.38])
    primary_category = gender
    accepts = rng.choice(["true", "false", "blank"], p=[0.62, 0.30, 0.08])
    return CustomerProfile(
        customer_id=str(1000000 + serial),
        canonical_email=email,
        first_name=first_name,
        last_name=last_name,
        created_at=created_at,
        updated_at=created_at + pd.Timedelta(days=int(rng.integers(3, 120))),
        city=city,
        state=state,
        state_code=state_code,
        zip_code=zip_code(rng),
        accepts_marketing=None if accepts == "blank" else accepts,
        acquisition_channel=ch[0],
        source=ch[1],
        medium=ch[2],
        source_platform=ch[3],
        segment=segment,
        gender=gender,
        primary_category=primary_category,
        promo_acquired=promo_acquired,
        email_drift=bool(rng.random() < 0.02),
        guest_fragmentation=bool(rng.random() < 0.015),
    )


# --------------------------------------------------------------------------- orders
def build_one_order(rng, order_serial, line_item_serial, customer, ts, subscription_order, welcome, units, forced_product=None):
    """Build one order + its line items for a target unit count (AOV controller decides units).

    `forced_product` makes subscription renewals reorder the same subscribed SKU.
    """
    disc = SUBSCRIPTION_DISCOUNT if subscription_order else (WELCOME_DISCOUNT if welcome else 0.0)
    order_id = str(700000000 + order_serial)
    order_name = f"#LUM{200000 + order_serial}"

    lines: list[dict] = []
    gross = 0.0
    discount_total = 0.0
    li = line_item_serial

    def add_line(product, qty):
        nonlocal gross, discount_total, li
        list_price = float(product["base_price"])
        sell_price = round(list_price * (1.0 - disc), 2)
        unit_disc = round(list_price - sell_price, 2)
        gross += list_price * qty
        discount_total += unit_disc * qty
        sub_eligible = bool(product["subscription_eligible"]) and subscription_order
        lines.append(
            {
                "order_id": order_id,
                "line_item_id": f"gid://shopify/LineItem/{900000000 + li}",
                "admin_graphql_api_id": f"gid://shopify/LineItem/{900000000 + li}",
                "product_id": product["product_id"],
                "variant_id": product["variant_id"],
                "sku": product["sku"],
                "title": product["title"],
                "variant_title": "Default Title",
                "vendor": "Luminary Vitamins",
                "product_type": product["category"],
                "quantity": qty,
                "price": round(list_price, 2),
                "discounted_price": sell_price,
                "total_discount": round(unit_disc * qty, 2),
                "taxable": True,
                "requires_shipping": True,
                "fulfillment_status": "fulfilled",
                "selling_plan_name": "Subscribe & Save" if sub_eligible else pd.NA,
                "selling_plan_id": (
                    f"sp_{hashlib.sha1(str(product['sku']).encode()).hexdigest()[:10]}" if sub_eligible else pd.NA
                ),
            }
        )
        li += 1

    if units >= 2 and rng.random() < 0.35:
        # His & Hers bundle (counts as ~2 units of value) as a single line.
        bundle = next((p for p in active_products_for_date(ts) if p["category"] == "bundle"), None)
        if bundle is not None:
            add_line(bundle, 1)
            units -= 2
    while units > 0:
        product = forced_product if forced_product is not None else _pick_product(rng, ts, customer.gender, allow_bundle=False)
        qty = min(units, 1 + (1 if rng.random() < 0.12 else 0))
        add_line(product, qty)
        units -= qty
    if not lines:
        add_line(_pick_product(rng, ts, customer.gender, allow_bundle=False), 1)

    total_line_items_price = round(gross, 2)
    total_discounts = round(discount_total, 2)
    total_price = round(max(0.5, total_line_items_price - total_discounts), 2)
    total_tax = round(total_price * 0.07, 2)  # US sales tax, added at checkout (not in total_price)

    month_key = ts.strftime("%Y-%m")
    refund_rate = MONTHLY_REFUND_RATE[month_key] + (0.004 if customer.promo_acquired else 0.0)
    refund_status, refunded_amount, financial_status = "none", 0.0, "paid"
    if rng.random() < refund_rate:
        if rng.random() < 0.55:
            refund_status, refunded_amount, financial_status = "full", total_price, "refunded"
        else:
            # Partial refund: some rows intentionally omit the amount (data issue).
            refund_status, financial_status = "partial", "partially_refunded"
            refunded_amount = 0.0 if rng.random() < 0.18 else round(total_price * rng.uniform(0.2, 0.7), 2)

    order_row = {
        "id": order_id,
        "admin_graphql_api_id": f"gid://shopify/Order/{700000000 + order_serial}",
        "order_number": 200000 + order_serial,
        "name": order_name,
        "customer_id": customer.customer_id,
        "email": customer.canonical_email,
        "created_at": to_iso(ts),
        "processed_at": to_iso(ts + pd.Timedelta(minutes=int(rng.integers(2, 35)))),
        "updated_at": to_iso(ts + pd.Timedelta(hours=int(rng.integers(6, 96)))),
        "currency": "USD",
        "presentment_currency": "USD",
        "financial_status": financial_status,
        "fulfillment_status": "fulfilled",
        "subtotal_price": total_price,
        "total_discounts": total_discounts,
        "total_tax": total_tax,
        "total_shipping_price_set_amount": 0.0,  # blanket free US shipping
        "total_price": total_price,
        "total_line_items_price": total_line_items_price,
        "taxes_included": False,
        "total_weight": int(180 * sum(int(line["quantity"]) for line in lines)),
        "line_items_count": int(sum(int(line["quantity"]) for line in lines)),
        "billing_address_country": "United States",
        "billing_address_country_code": "US",
        "billing_address_city": customer.city,
        "billing_address_province": customer.state,
        "billing_address_zip": customer.zip_code,
        "source_name": "web",
        "refunded_amount": round(refunded_amount, 2),
        "refund_status": refund_status,
    }
    return order_row, lines


def churn_hazard(tenure: int) -> float:
    """Monthly probability an active subscription cancels, by tenure (months since start).

    Front-loaded fertility lifecycle: people take it for a few months while trying to
    conceive, then churn on the outcome (conception/birth) or after giving up.
    """
    if tenure <= 2:
        return 0.13
    if tenure <= 5:
        return 0.19
    if tenure <= 9:
        return 0.24
    return 0.30


def build_core_sources():
    """Recurring-subscription order engine.

    Each month's fixed order target is composed of (a) subscription renewals from the
    surviving active base, (b) occasional one-time repeats from past non-subscribers, and
    (c) new customers (a floor share keeps acquisition going). Renewals are capacity-limited
    so they never exceed the target; surplus subscribers simply skip that cycle (realistic
    for Loop). Orders/buyer therefore rises well above 1 and retention declines with churn.
    """
    rng = np.random.default_rng(SEED)
    profiles: dict[str, CustomerProfile] = {}
    active_subs: dict[str, dict] = {}      # customer_id -> {"start_idx": int, "product": dict}
    ever_subscribed: set[str] = set()
    nonsub_buyers: list[str] = []
    order_rows: list[dict] = []
    line_rows: list[dict] = []
    name_pool: list[str] = []
    cs = os = li = 1

    for midx, month_key in enumerate(MONTH_KEYS):
        target_orders = int(round(MONTHLY_ORDER_TARGETS[month_key] * ROW_SCALE))
        target_aov = MONTHLY_AOV[month_key]

        def emit(customer, ts, subscription_order, welcome, forced_product=None):
            nonlocal os, li
            # Size each order so E[total_price] == the month's AOV target, given this
            # order's own discount: P(2 units) = target/unit_net - 1.
            disc = SUBSCRIPTION_DISCOUNT if subscription_order else (WELCOME_DISCOUNT if welcome else 0.0)
            unit_net = 89.0 * (1.0 - disc)
            p_double = min(0.9, max(0.0, target_aov / unit_net - 1.0))
            units = 2 if rng.random() < p_double else 1
            order_row, lines = build_one_order(
                rng, os, li, customer, ts, subscription_order, welcome, units, forced_product=forced_product
            )
            if name_pool and rng.random() < 0.002:  # rare duplicate-looking order name
                order_row["name"] = name_pool[int(rng.integers(0, len(name_pool)))]
            name_pool.append(order_row["name"])
            order_rows.append(order_row)
            line_rows.extend(lines)
            li += len(lines)
            os += 1

        # 1. Churn the active subscription base (tenure-based hazard).
        for cid in list(active_subs):
            if churn_hazard(midx - active_subs[cid]["start_idx"]) > rng.random():
                del active_subs[cid]

        # 2. Renewals — capacity-limited so a floor of new acquisition + adhoc still fits.
        adhoc_target = int(round(ADHOC_REPEAT_SHARE * target_orders))
        min_new = max(1, int(round(MIN_NEW_SHARE * target_orders)))
        max_renewals = max(0, target_orders - min_new - adhoc_target)
        renewal_ids = list(active_subs.keys())
        if len(renewal_ids) > max_renewals:
            renewal_ids = [str(x) for x in rng.choice(renewal_ids, size=max_renewals, replace=False)]
        for cid in renewal_ids:
            customer = profiles[cid]
            ts = random_timestamp_after(rng, month_key, customer.created_at)
            emit(customer, ts, subscription_order=True, welcome=False, forced_product=active_subs[cid]["product"])
        renewals = len(renewal_ids)

        # 3. One-time repeats from past non-subscribers.
        adhoc_count = min(adhoc_target, max(0, target_orders - renewals - min_new))
        if nonsub_buyers and adhoc_count > 0:
            for cid in (str(x) for x in rng.choice(nonsub_buyers, size=adhoc_count, replace=True)):
                customer = profiles[cid]
                ts = random_timestamp_after(rng, month_key, customer.created_at)
                emit(customer, ts, subscription_order=False, welcome=False)
        else:
            adhoc_count = 0

        # 4. New customers fill the remainder; a share start a subscription.
        new_count = max(0, target_orders - renewals - adhoc_count)
        for _ in range(new_count):
            ts = random_timestamp_in_month(rng, month_key)
            customer = create_customer_profile(rng, cs, ts, promo_acquired=False)
            cs += 1
            subscribes = bool(rng.random() < SUB_CONVERSION)
            welcome = (not subscribes) and bool(rng.random() < WELCOME_USE_RATE)
            customer.promo_acquired = welcome or subscribes
            profiles[customer.customer_id] = customer
            if subscribes:
                product = _pick_product(rng, ts, customer.gender, allow_bundle=False)
                active_subs[customer.customer_id] = {"start_idx": midx, "product": product}
                ever_subscribed.add(customer.customer_id)
                emit(customer, ts, subscription_order=True, welcome=False, forced_product=product)
            else:
                nonsub_buyers.append(customer.customer_id)
                emit(customer, ts, subscription_order=False, welcome=welcome)

    # Non-buyer prospects (exist in Klaviyo/GA4 but never purchased).
    for _ in range(int(round(len(profiles) * 0.15))):
        month_key = MONTH_KEYS[int(rng.integers(0, len(MONTH_KEYS)))]
        ts = random_timestamp_in_month(rng, month_key)
        customer = create_customer_profile(rng, cs, ts, promo_acquired=False)
        profiles[customer.customer_id] = customer
        cs += 1

    profiles_df = pd.DataFrame([vars(p) for p in profiles.values()])
    customers_df = build_shopify_customers(profiles_df, rng)
    orders_df = pd.DataFrame(order_rows).sort_values("created_at").reset_index(drop=True)
    order_items_df = pd.DataFrame(line_rows).reset_index(drop=True)
    return customers_df, orders_df, order_items_df, profiles_df, ever_subscribed


def build_shopify_customers(profiles: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    for row in profiles.itertuples(index=False):
        display_email = drift_email(row.canonical_email, rng) if row.email_drift else row.canonical_email
        rows.append(
            {
                "id": row.customer_id,
                "email": display_email,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "phone": f"+1{int(rng.integers(2000000000, 9999999999))}",
                "created_at": to_iso(row.created_at),
                "updated_at": to_iso(max(row.updated_at, row.created_at)),
                "state": "enabled",
                "verified_email": True,
                "tax_exempt": False,
                "tags": "",
                "currency": "USD",
                "accepts_marketing": row.accepts_marketing,
                "default_address_city": row.city,
                "default_address_province": row.state,
                "default_address_province_code": row.state_code,
                "default_address_country": "United States",
                "default_address_country_code": "US",
                "default_address_zip": row.zip_code,
            }
        )
    return pd.DataFrame(rows).sort_values("created_at").reset_index(drop=True)


# --------------------------------------------------------------------------- GA4
def _ga4_channel(rng, profile, ts):
    if rng.random() < 0.08:
        return ("Unassigned", "Unassigned", "(direct)", "(none)", "Direct")
    return (
        str(profile["acquisition_channel"]),
        str(profile["acquisition_channel"]),
        str(profile["source"]),
        str(profile["medium"]),
        str(profile["source_platform"]),
    )


GA4_DIRECT = ("Direct", "Direct", "(direct)", "(none)", "Direct")
GA4_NOTSET = ("Unassigned", "Unassigned", "(not set)", "(not set)", "(not set)")


def build_ga4(orders, order_items, profiles):
    rng = np.random.default_rng(SEED + 11)
    profile_map = profiles.set_index("customer_id").to_dict("index")
    item_map = {str(oid): g.to_dict("records") for oid, g in order_items.groupby("order_id", sort=False)}
    # Renewal orders are server-side recurring charges with no web session: they mostly
    # bypass the GA4 web pixel, and when captured carry no acquisition channel. Subscription
    # *signups* (the customer's first order) are real web checkouts and keep attribution.
    sub_ids = set(order_items.loc[order_items["selling_plan_id"].notna(), "order_id"].astype(str))
    first_ids = set(orders.sort_values("created_at").groupby("customer_id").head(1)["id"].astype(str))
    order_rows, item_rows = [], []
    for order in orders.itertuples(index=False):
        is_renewal = str(order.id) in sub_ids and str(order.id) not in first_ids
        if is_renewal:
            if rng.random() >= 0.10:  # most renewals never reach GA4 (no web checkout)
                continue
            ch = GA4_DIRECT if rng.random() < 0.7 else GA4_NOTSET
        else:
            if rng.random() < 0.07:  # web orders: small tag/consent loss
                continue
            created = pd.Timestamp(order.created_at)
            ch = _ga4_channel(rng, profile_map[str(order.customer_id)], created)
        created = pd.Timestamp(order.created_at)
        gts = created + pd.Timedelta(minutes=int(rng.integers(-18, 18)))
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
                "country": "United States",
                "region": order.billing_address_province,
                "city": order.billing_address_city,
                "streamId": "201900777",
                "platform": "web",
                "user_id": order.customer_id if rng.random() < 0.9 else pd.NA,
                "itemPromotionId": pd.NA,
                "itemPromotionName": pd.NA,
                "purchaseRevenue": round(order.total_price - order.refunded_amount, 2),
                "grossPurchaseRevenue": order.total_price,
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
                    "itemBrand": "Luminary Vitamins",
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
                    "itemRefundAmount": round(order.refunded_amount / max(1, len(items)), 2) if order.refunded_amount else 0.0,
                    "itemDiscountAmount": round(float(item["total_discount"]), 2),
                    "itemsPurchased": int(item["quantity"]),
                    "itemPurchaseQuantity": int(item["quantity"]),
                }
            )
    return pd.DataFrame(order_rows), pd.DataFrame(item_rows)


# --------------------------------------------------------------------------- Klaviyo
EMAIL_FLOW_METRICS = ["Received Email", "Opened Email", "Clicked Email"]
SMS_FLOW_METRICS = ["Received SMS", "Clicked SMS"]


def build_klaviyo_events(orders, profiles, subscribers):
    rng = np.random.default_rng(SEED + 23)
    profile_map = profiles.set_index("customer_id", drop=False).to_dict("index")
    recent = orders[pd.to_datetime(orders["created_at"]) >= KLAVIYO_START_TS]
    # First order per customer — used to avoid crediting auto-renewals as Klaviyo conversions.
    first_ids = set(orders.sort_values("created_at").groupby("customer_id").head(1)["id"].astype(str))
    rows = []
    eid = 1
    metric_ids = {
        "Received Email": "RXEM", "Opened Email": "OPEM", "Clicked Email": "CLEM",
        "Received SMS": "RXSM", "Clicked SMS": "CLSM", "Placed Order": "PLOR",
    }
    flows = [
        ("Welcome Series", "flow_welcome"),
        ("Post-Purchase Nurture", "flow_postpurchase"),
        ("Subscription Reminder", "flow_subreminder"),
        ("Abandoned Checkout", "flow_abandoned"),
    ]
    campaigns = [
        ("Fertility Education Newsletter", "cmp_edu"),
        ("Sperm Health Awareness", "cmp_sperm"),
        ("Prenatal Guide", "cmp_prenatal"),
    ]

    def emit(profile, base_ts, metric, channel, flow=None, campaign=None, value=None, attributed_channel=None):
        nonlocal eid
        if base_ts < KLAVIYO_START_TS or base_ts > WINDOW_END_TS:
            return  # keep the email/SMS stream inside the modeling window
        email = drift_email(profile["canonical_email"], rng) if profile["email_drift"] else profile["canonical_email"]
        rows.append(
            {
                "event_id": f"01J{eid:012d}",
                "timestamp": to_iso(base_ts),
                "metric_id": metric_ids.get(metric, "MISC"),
                "metric_name": metric,
                "profile_id": f"prof_{profile['customer_id']}",
                "email": email,
                "phone_number": f"+1{1000000000 + int(profile['customer_id']) % 8999999999}" if channel == "sms" else pd.NA,
                "channel": channel,
                "$message": f"msg_{eid % 9000}",
                "campaign_id": campaign[1] if campaign else pd.NA,
                "campaign_name": campaign[0] if campaign else pd.NA,
                "$flow": flow[1] if flow else pd.NA,
                "$flow_message_id": f"{flow[1]}_m1" if flow else pd.NA,
                "flow_name": flow[0] if flow else pd.NA,
                "subject": "Your fertility journey with Luminary" if channel == "email" else pd.NA,
                "$variation": pd.NA,
                "url": "https://www.luminaryvitamins.com/" if metric in ("Clicked Email", "Clicked SMS") else pd.NA,
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

    # Post-purchase + subscription flows triggered around recent orders.
    for order in recent.itertuples(index=False):
        profile = profile_map[str(order.customer_id)]
        if not profile["accepts_marketing"] or profile["accepts_marketing"] == "false":
            if rng.random() < 0.7:
                continue
        order_ts = pd.Timestamp(order.created_at)
        is_sub = str(order.customer_id) in subscribers
        is_renewal = is_sub and str(order.id) not in first_ids
        flow = flows[1] if not is_sub else flows[2]
        base = order_ts + pd.Timedelta(hours=int(rng.integers(1, 36)))
        # Email flow sequence.
        emit(profile, base, "Received Email", "email", flow=flow)
        if rng.random() < 0.52:
            emit(profile, base + pd.Timedelta(hours=int(rng.integers(1, 20))), "Opened Email", "email", flow=flow)
            if rng.random() < 0.32:
                emit(profile, base + pd.Timedelta(hours=int(rng.integers(2, 30))), "Clicked Email", "email", flow=flow)
        # SMS for a subset who opted into SMS.
        if rng.random() < 0.22:
            sbase = order_ts + pd.Timedelta(days=int(rng.integers(20, 45)))
            if sbase >= KLAVIYO_START_TS:
                emit(profile, sbase, "Received SMS", "sms", flow=flows[2])
                if rng.random() < 0.14:
                    emit(profile, sbase + pd.Timedelta(hours=int(rng.integers(1, 8))), "Clicked SMS", "sms", flow=flows[2])
        # Klaviyo-attributed conversion — only for click-driven (non-renewal) orders.
        # Auto-renewals are not credited to email/SMS even though Klaviyo tracks the order.
        if not is_renewal and rng.random() < 0.14:
            emit(
                profile, order_ts, "Placed Order", "email", flow=flow,
                value=float(order.total_price),
                attributed_channel="email" if rng.random() < 0.7 else "sms",
            )

    # Monthly campaign blasts to a sample of marketable profiles.
    marketable = [p for p in profile_map.values() if p["accepts_marketing"] == "true"]
    for month_key in MONTH_KEYS:
        m_start = month_start(month_key)
        if m_start < KLAVIYO_START_TS:
            continue
        campaign = campaigns[int(rng.integers(0, len(campaigns)))]
        sample = rng.choice(len(marketable), size=min(len(marketable), 1200), replace=False)
        send_ts = m_start + pd.Timedelta(days=int(rng.integers(2, 26)), hours=int(rng.integers(8, 18)))
        for i in sample:
            profile = marketable[int(i)]
            emit(profile, send_ts, "Received Email", "email", campaign=campaign)
            if rng.random() < 0.34:
                emit(profile, send_ts + pd.Timedelta(hours=int(rng.integers(1, 30))), "Opened Email", "email", campaign=campaign)
                if rng.random() < 0.18:
                    emit(profile, send_ts + pd.Timedelta(hours=int(rng.integers(2, 40))), "Clicked Email", "email", campaign=campaign)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Meta Ads
def build_meta_ads():
    rng = np.random.default_rng(SEED + 31)
    account_id, account_name = "act_5567788", "Luminary Vitamins"
    start = pd.Timestamp(META_START, tz="UTC")
    end = pd.Timestamp(SOURCE_WINDOW_END, tz="UTC")
    # campaign, objective
    campaigns = [
        ("Prospecting - Female Fertility", "OUTCOME_SALES", "female"),
        ("Prospecting - Male Sperm Health", "OUTCOME_SALES", "male"),
        ("Prospecting - Prenatal", "OUTCOME_SALES", "female"),
        ("Retargeting - Site Visitors", "OUTCOME_SALES", "all"),
        ("Awareness - Brand", "OUTCOME_AWARENESS", "all"),
    ]
    insight_rows, creative_rows = [], []
    cta_types = ["SHOP_NOW", "LEARN_MORE", "SIGN_UP"]
    obj_formats = ["VIDEO", "SHARE", "PHOTO"]
    cid_n, aid_n, adid_n = 5000, 6000, 7000

    for c_i, (cname, objective, seg) in enumerate(campaigns):
        campaign_id = f"{120000000000000000 + cid_n + c_i}"
        n_adsets = 2 if "Awareness" in cname else 3
        # Campaign launch staggered across the historic window.
        c_launch = start + pd.Timedelta(days=int(rng.integers(0, 120)) + c_i * 20)
        for a_i in range(n_adsets):
            adset_id = f"{120000000000000000 + aid_n}"
            aid_n += 1
            adset_name = f"{seg.title()} | {['Broad','Lookalike','Interest','Retarget'][a_i % 4]}"
            n_ads = int(rng.integers(2, 5))
            for _ in range(n_ads):
                ad_id = f"{120000000000000000 + adid_n}"
                adid_n += 1
                creative_id = f"crv_{adid_n}"
                ad_launch = max(c_launch, start) + pd.Timedelta(days=int(rng.integers(0, 200)))
                ad_name = f"{seg}_{obj_formats[adid_n % 3].lower()}_{adid_n}"
                creative_rows.append(
                    {
                        "ad_id": ad_id,
                        "creative_id": creative_id,
                        "creative_name": f"{cname} creative {adid_n}",
                        "object_type": obj_formats[adid_n % 3],
                        "call_to_action_type": cta_types[adid_n % 3],
                        "title": "Doctor-formulated fertility support",
                        "body": "Clinically-backed gummies for every stage of the journey.",
                        "thumbnail_url": f"https://scontent.example/{creative_id}.jpg",
                        "instagram_permalink_url": f"https://instagram.com/p/{creative_id}",
                        "effective_object_story_id": f"{campaign_id}_{adid_n}",
                    }
                )
                # Daily insights over the ad's active window.
                ad_end = end if rng.random() < 0.6 else ad_launch + pd.Timedelta(days=int(rng.integers(60, 320)))
                ad_end = min(ad_end, end)
                base_spend = float(rng.uniform(25, 140)) * (1.6 if "Prospecting" in cname else 1.0)
                for day in pd.date_range(ad_launch.normalize(), ad_end.normalize(), freq="D", tz="UTC"):
                    # Growth ramp over time + weekday noise.
                    progress = (day - start).days / max(1, (end - start).days)
                    spend = round(base_spend * (0.5 + 1.4 * progress) * float(rng.uniform(0.7, 1.3)), 2)
                    if spend < 1:
                        continue
                    impressions = int(spend / float(rng.uniform(0.008, 0.018)))
                    clicks = int(impressions * float(rng.uniform(0.008, 0.022)))
                    link_clicks = int(clicks * float(rng.uniform(0.7, 0.95)))
                    reach = int(impressions * float(rng.uniform(0.55, 0.8)))
                    purchases = max(0, int(link_clicks * float(rng.uniform(0.02, 0.06))))
                    purchase_value = round(purchases * float(rng.uniform(89, 150)), 2)
                    roas = round(purchase_value / spend, 3) if spend else 0.0
                    insight_rows.append(
                        {
                            "date_start": day.strftime("%Y-%m-%d"),
                            "date_stop": day.strftime("%Y-%m-%d"),
                            "account_id": account_id,
                            "account_name": account_name,
                            "account_currency": "USD",
                            "campaign_id": campaign_id,
                            "campaign_name": cname,
                            "objective": objective,
                            "adset_id": adset_id,
                            "adset_name": adset_name,
                            "ad_id": ad_id,
                            "ad_name": ad_name,
                            "impressions": impressions,
                            "reach": reach,
                            "frequency": round(impressions / reach, 2) if reach else 0.0,
                            "clicks": clicks,
                            "inline_link_clicks": link_clicks,
                            "spend": spend,
                            "cpc": round(spend / clicks, 2) if clicks else 0.0,
                            "cpm": round(spend / impressions * 1000, 2) if impressions else 0.0,
                            "ctr": round(clicks / impressions * 100, 3) if impressions else 0.0,
                            "actions": json.dumps(
                                [
                                    {"action_type": "link_click", "value": str(link_clicks)},
                                    {"action_type": "landing_page_view", "value": str(int(link_clicks * 0.8))},
                                    {"action_type": "omni_purchase", "value": str(purchases)},
                                ]
                            ),
                            "action_values": json.dumps([{"action_type": "omni_purchase", "value": f"{purchase_value:.2f}"}]),
                            "purchase_roas": json.dumps([{"action_type": "omni_purchase", "value": f"{roas:.3f}"}]),
                        }
                    )
    return pd.DataFrame(insight_rows), pd.DataFrame(creative_rows)


# --------------------------------------------------------------------------- Google Ads
def build_google_ads():
    """Future-only: Google Ads keyword block lifted ~2026-05-25, so data starts then."""
    rng = np.random.default_rng(SEED + 41)
    start = GOOGLE_START_TS
    end = pd.Timestamp(SOURCE_WINDOW_END, tz="UTC")
    account_id, account_name = "8841007722", "Luminary Vitamins"
    campaigns = [
        ("Brand", "SEARCH", "TARGET_SPEND", 30),
        ("Fertility Non-Brand", "SEARCH", "MAXIMIZE_CONVERSIONS", 220),
        ("Sperm Health", "SEARCH", "MAXIMIZE_CONVERSIONS", 160),
        ("Prenatal", "SEARCH", "MAXIMIZE_CONVERSIONS", 140),
        ("Performance Max", "PERFORMANCE_MAX", "MAXIMIZE_CONVERSION_VALUE", 180),
    ]
    rows = []
    for c_i, (cname, channel_type, bidding, base_spend) in enumerate(campaigns):
        campaign_id = f"{2200000000 + c_i}"
        for day in pd.date_range(start.normalize(), end.normalize(), freq="D", tz="UTC"):
            progress = (day - start).days / max(1, (end - start).days)
            # Spend ramps as the newly-unblocked account scales.
            spend = round(base_spend * (0.3 + 1.5 * progress) * float(rng.uniform(0.75, 1.25)), 2)
            if spend < 1:
                continue
            cost_micros = int(round(spend * 1_000_000))
            impressions = int(spend / float(rng.uniform(0.01, 0.03)))
            clicks = int(impressions * float(rng.uniform(0.03, 0.08) if cname == "Brand" else rng.uniform(0.01, 0.03)))
            conversions = round(clicks * float(rng.uniform(0.03, 0.09)), 2)
            conv_value = round(conversions * float(rng.uniform(89, 150)), 2)
            rows.append(
                {
                    "segments.date": day.strftime("%Y-%m-%d"),
                    "customer.id": account_id,
                    "customer.descriptive_name": account_name,
                    "customer.currency_code": "USD",
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
                    "metrics.all_conversions": round(conversions * 1.15, 2),
                    "metrics.all_conversions_value": round(conv_value * 1.15, 2),
                    "metrics.ctr": round(clicks / impressions, 4) if impressions else 0.0,
                    "metrics.average_cpc": int(round(cost_micros / clicks)) if clicks else 0,
                    "metrics.average_cpm": int(round(cost_micros / impressions * 1000)) if impressions else 0,
                    "metrics.search_impression_share": round(float(rng.uniform(0.18, 0.62)), 4) if channel_type == "SEARCH" else pd.NA,
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Zendesk
def build_zendesk_tickets(orders, profiles):
    rng = np.random.default_rng(SEED + 51)
    profile_map = profiles.set_index("customer_id").to_dict("index")
    subjects = [
        ("Subscription frequency change", "subscription"),
        ("When should I take these gummies?", "product_usage"),
        ("Where is my order?", "shipping"),
        ("Ingredient / allergen question", "ingredients"),
        ("Can I take this while pregnant?", "clinical_question"),
        ("Cancel my subscription", "cancellation"),
    ]
    sample = orders.sample(frac=0.035, random_state=SEED).reset_index(drop=True)
    rows = []
    for idx, order in enumerate(sample.itertuples(index=False), start=1):
        profile = profile_map[str(order.customer_id)]
        subject, tag = subjects[int(rng.integers(0, len(subjects)))]
        created = pd.Timestamp(order.created_at) + pd.Timedelta(days=int(rng.integers(1, 18)))
        updated = created + pd.Timedelta(hours=int(rng.integers(2, 96)))
        status = "open" if rng.random() < 0.2 else "solved"
        if rng.random() < 0.04:  # mild status-casing drift (data issue)
            status = status.upper()
        rows.append(
            {
                "id": 800000 + idx,
                "created_at": to_iso(created),
                "updated_at": to_iso(updated),
                "status": status,
                "priority": weighted_choice(rng, ["normal", "high", "urgent"], [0.76, 0.2, 0.04], 1)[0],
                "type": "question",
                "subject": subject,
                "description": f"Customer support query linked to order {order.name}.",
                "requester_id": int(order.customer_id),
                "submitter_id": int(order.customer_id),
                "assignee_id": 9000 + int(rng.integers(1, 25)),
                "organization_id": 1,
                "group_id": 100 + int(rng.integers(1, 6)),
                "via_channel": weighted_choice(rng, ["email", "web", "chat"], [0.6, 0.28, 0.12], 1)[0],
                "ticket_form_id": 301,
                "brand_id": 4501,
                "recipient": profile["canonical_email"],
                "tags": f"customer,{tag}",
                "satisfaction_score": weighted_choice(rng, ["good", "bad", "offered"], [0.7, 0.06, 0.24], 1)[0],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- main
def write_outputs(output_map):
    for filename, df in output_map.items():
        path = write_source_csv(df, BUSINESS, filename)
        print_source_summary(f"{BUSINESS} {filename}", len(df), path)


def main() -> None:
    ensure_workspace_dirs()
    products_df = build_products()
    customers_df, orders_df, order_items_df, profiles_df, subscribers = build_core_sources()
    ga4_orders_df, ga4_items_df = build_ga4(orders_df, order_items_df, profiles_df)
    klaviyo_df = build_klaviyo_events(orders_df, profiles_df, subscribers)
    meta_insights_df, meta_creatives_df = build_meta_ads()
    google_ads_df = build_google_ads()
    zendesk_df = build_zendesk_tickets(orders_df, profiles_df)

    write_outputs(
        {
            "shopify_products.csv": products_df,
            "shopify_orders.csv": orders_df,
            "shopify_customers.csv": customers_df,
            "shopify_order_items.csv": order_items_df,
            "ga4_reporting_purchase_events.csv": ga4_orders_df,
            "ga4_reporting_purchase_items.csv": ga4_items_df,
            "klaviyo_events.csv": klaviyo_df,
            "meta_ads_insights.csv": meta_insights_df,
            "meta_ad_creatives.csv": meta_creatives_df,
            "google_ads_campaign_performance.csv": google_ads_df,
            "zendesk_tickets.csv": zendesk_df,
        }
    )


if __name__ == "__main__":
    main()
