# Channel-Mix Realism Benchmarks

Use this when assigning acquisition channels and modelling attribution (GA4, Triple Whale,
ad-platform exports). The goal is a believable, **non-uniform** channel mix. A uniform split
across channels is the single most common tell that attribution data is synthetic.

## Default D2C acquisition mix

Paid-heavy consumer D2C brand (the typical case for these pitches). Weights should sum to ~1.0
and skew hard toward paid acquisition:

| Channel | Share | Notes |
|---|---|---|
| Paid Social | 28–32% | usually the largest single channel for D2C |
| Paid Search | 20–26% | brand + non-brand |
| Organic Search | 12–16% | |
| Direct | 10–14% | brand strength; grows with maturity |
| Email / CRM | 8–12% | owned channel; higher for subscription-led brands |
| Affiliate | 6–10% | |

Adjust to the brief: heavy-TV or influencer brands carry more Direct/Organic; marketplace-led
brands differ entirely. Record the chosen weights as an explicit assumption.

## Unattributed / unassigned share

- **Baseline unattributed share should be ~7–10%**, not higher. This is the steady-state floor
  of `(not set)` / `Unassigned` / direct-with-no-source traffic.
- Do **not** stack multiple independent "unattributed" code paths on top of each other — a
  small per-row `(not set)` probability *plus* a baseline tracking-gap probability silently
  doubles the floor. Keep one floor (~1–2% structural) and let modelled tracking breaks
  account for the rest.

## Channel-tracking breaks (modelled inflection points)

When the brief calls for tracking breakage:

- Raise unattributed share to **~19–25%** for short windows (roughly 7–10 days each).
- Keep them sparse (a handful across the horizon) and tie them to plausible causes
  (tag-manager change, consent update, GA4/Triple Whale implementation hiccup).
- The break should be visibly above baseline but not swallow the whole period.

## Partial attribution coverage (a real coverage gap, not just a label)

If "partial attribution coverage" is a selected data issue, model it as **genuinely missing
rows**, not merely a channel value of `unattributed`:

- Drop **5–12% of in-window orders entirely** from the attribution source (e.g. Triple Whale),
  so those orders exist in commerce but never join downstream. This is what forces an analyst
  to reconcile, and it is the believable signature of a recently implemented attribution tool.
- Optionally, of the orders that *are* present, leave a smaller slice (~5–7%) with an
  `unattributed` channel.
- The attribution source must still only reference **real** order/customer keys — a coverage
  gap means *fewer* rows, never *orphan* rows.

## Cross-system consistency

- GA4 ecommerce purchase tracking is usually near-complete (≈1 row per order); the *attribution*
  is what's missing (channel = Unassigned), not the purchase event itself.
- Triple Whale is the source where genuine coverage gaps are believable.
- A customer's acquisition channel should be reasonably stable across systems; session-level
  channel can differ from the acquisition channel, but not randomly on every event.
