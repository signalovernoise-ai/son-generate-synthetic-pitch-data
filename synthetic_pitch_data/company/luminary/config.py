from __future__ import annotations

from dataclasses import dataclass


BUSINESS = "luminary"
SEED = 20260531
# No operational scaling: projected raw build (~1.6M rows) is well under the 5M gate.
ROW_SCALE = 1.0

# Default modeling window: 18 historic + 6 future months (today 2026-05-31).
SOURCE_WINDOW_START = "2024-12-01"
SOURCE_WINDOW_END = "2026-11-30"

# Source-specific windows.
KLAVIYO_START = "2025-06-01"          # email/SMS stream trimmed to last 12 months
META_START = "2024-12-01"             # Meta is the primary live paid channel, full window
GOOGLE_ADS_START = "2026-05-25"       # Google Ads keyword block ("sperm") just unblocked: future-only


@dataclass(frozen=True)
class ProductSpec:
    sku: str
    title: str
    category: str          # male | female | unisex | bundle
    base_price: float
    compare_at_price: float  # equals base_price — clinical positioning, no list-price discount
    subscription_eligible: bool
    current: bool
    launch_date: str
    retire_date: str | None = None


# Live catalog from products.json (2026-05-31): 9 gummy SKUs @ $89 + His & Hers Bundle @ $178.
# Plus two adjacent legacy/delisted items grounded in older "Create"/"Thrive" naming.
PRODUCTS: list[ProductSpec] = [
    ProductSpec("LUM-SPERM-SUPPORT", "Sperm Support Gummies", "male", 89.00, 89.00, True, True, "2024-11-01"),
    ProductSpec("LUM-MENS-WELLBEING", "Men's Wellbeing Gummies", "male", 89.00, 89.00, True, True, "2024-11-01"),
    ProductSpec("LUM-PRECONCEPTION", "Preconception Gummies", "female", 89.00, 89.00, True, True, "2024-11-01"),
    ProductSpec("LUM-EGG-SUPPORT", "Egg Support Gummies", "female", 89.00, 89.00, True, True, "2024-11-01"),
    ProductSpec("LUM-PREGNANCY", "Pregnancy Gummies", "female", 89.00, 89.00, True, True, "2025-02-01"),
    ProductSpec("LUM-POSTPARTUM", "Postpartum Gummies", "female", 89.00, 89.00, True, True, "2025-06-01"),
    ProductSpec("LUM-HORMONAL-PCOS", "Hormonal Health & PCOS Gummies", "female", 89.00, 89.00, True, True, "2025-03-01"),
    ProductSpec("LUM-WELLBEING", "Wellbeing Gummies", "unisex", 89.00, 89.00, True, True, "2025-01-01"),
    ProductSpec("LUM-HIS-HERS-BUNDLE", "His & Hers Fertility Bundle", "bundle", 178.00, 178.00, False, True, "2025-01-15"),
    # Legacy / delisted, kept adjacent to the current assortment.
    ProductSpec("LUM-CREATE-MEN-LEGACY", "Create for Men", "male", 89.00, 89.00, True, False, "2024-09-01", "2025-06-01"),
    ProductSpec("LUM-FERTILITY-DUO-LEGACY", "Fertility Starter Duo", "bundle", 169.00, 169.00, False, False, "2024-09-01", "2025-03-01"),
]


# Monthly order targets (promo-inclusive) — from the approved conservative trajectory.
MONTHLY_ORDER_TARGETS = {
    "2024-12": 1444,
    "2025-01": 1667,
    "2025-02": 1736,
    "2025-03": 1846,
    "2025-04": 1956,
    "2025-05": 2087,
    "2025-06": 2228,
    "2025-07": 2337,
    "2025-08": 2452,
    "2025-09": 2667,
    "2025-10": 2882,
    "2025-11": 3064,
    "2025-12": 3245,
    "2026-01": 3830,
    "2026-02": 4000,
    "2026-03": 4263,
    "2026-04": 4579,
    "2026-05": 4947,
    "2026-06": 5208,
    "2026-07": 5469,
    "2026-08": 5750,
    "2026-09": 5979,
    "2026-10": 6309,
    "2026-11": 6701,
}

# Per-month target AOV = revenue / orders from the approved trajectory (net of discount,
# shipping-excluded). The basket controller in generate_raw steers mean(total_price) to this.
MONTHLY_AOV = {
    "2024-12": 90.03,
    "2025-01": 89.98,
    "2025-02": 91.01,
    "2025-03": 91.01,
    "2025-04": 91.00,
    "2025-05": 91.99,
    "2025-06": 92.01,
    "2025-07": 92.00,
    "2025-08": 92.99,
    "2025-09": 92.99,
    "2025-10": 92.99,
    "2025-11": 94.00,
    "2025-12": 93.99,
    "2026-01": 94.00,
    "2026-02": 95.00,
    "2026-03": 95.00,
    "2026-04": 95.00,
    "2026-05": 95.01,
    "2026-06": 96.01,
    "2026-07": 95.99,
    "2026-08": 96.00,
    "2026-09": 97.01,
    "2026-10": 97.00,
    "2026-11": 97.00,
}

# New-customer order share: early ramp is acquisition-heavy, maturing toward more repeat.
MONTHLY_NEW_ORDER_SHARE = {
    "2024-12": 0.95,
    "2025-01": 0.92,
    "2025-02": 0.90,
    "2025-03": 0.88,
    "2025-04": 0.85,
    "2025-05": 0.82,
    "2025-06": 0.80,
    "2025-07": 0.79,
    "2025-08": 0.78,
    "2025-09": 0.77,
    "2025-10": 0.76,
    "2025-11": 0.75,
    "2025-12": 0.73,
    "2026-01": 0.71,
    "2026-02": 0.70,
    "2026-03": 0.69,
    "2026-04": 0.67,
    "2026-05": 0.66,
    "2026-06": 0.64,
    "2026-07": 0.63,
    "2026-08": 0.62,
    "2026-09": 0.61,
    "2026-10": 0.60,
    "2026-11": 0.60,
}

# Subscription order share (subscribe & save), rising as the brand matures.
MONTHLY_SUBSCRIPTION_SHARE = {
    "2024-12": 0.15,
    "2025-01": 0.16,
    "2025-02": 0.17,
    "2025-03": 0.18,
    "2025-04": 0.19,
    "2025-05": 0.20,
    "2025-06": 0.22,
    "2025-07": 0.23,
    "2025-08": 0.24,
    "2025-09": 0.25,
    "2025-10": 0.26,
    "2025-11": 0.27,
    "2025-12": 0.28,
    "2026-01": 0.30,
    "2026-02": 0.31,
    "2026-03": 0.32,
    "2026-04": 0.34,
    "2026-05": 0.35,
    "2026-06": 0.36,
    "2026-07": 0.37,
    "2026-08": 0.38,
    "2026-09": 0.39,
    "2026-10": 0.40,
    "2026-11": 0.40,
}

# Refund rate: ~4.0% baseline, ~4.5% in/after the spring promo window.
MONTHLY_REFUND_RATE = {m: 0.040 for m in MONTHLY_ORDER_TARGETS}
for _m in ("2026-04", "2026-05", "2026-06"):
    MONTHLY_REFUND_RATE[_m] = 0.045

# Subscribe & save discount and first-order welcome offer.
SUBSCRIPTION_DISCOUNT = 0.15
WELCOME_DISCOUNT = 0.10
WELCOME_USE_RATE = 0.45  # share of new, non-subscription first orders that redeem a welcome code
