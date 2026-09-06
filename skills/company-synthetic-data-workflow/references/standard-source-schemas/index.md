# Standard Source Schemas

Use this folder for platform-specific source schemas that define the expected raw extract shape by system.

Do not collapse source-shaped system data directly into analytical tables without documenting the mapping into the controlled stage layer.

Read the file for the relevant source system:

- `shopify.md`
- `zendesk.md`
- `ga4-reporting-api.md`
- `bloomreach.md`
- `klaviyo.md`
- `google-ads.md`
- `meta-ads.md`
- `tiktok-ads.md`
- `triple-whale.md`
- `ordergroove.md`
- `recharge.md`
- `skio.md`
- `gorgias.md`
- `custom-postgres.md`

Pick **one** system per domain per company, backed by evidence:

- subscriptions: `recharge.md`, `skio.md` or `ordergroove.md`
- campaign / lifecycle: `klaviyo.md` or `bloomreach.md`
- support: `gorgias.md` or `zendesk.md`

Paid media is the exception: `google-ads.md`, `meta-ads.md` and `tiktok-ads.md` all share the
`ad_performance` role and are **unioned**, not chosen between. Include every platform the evidence
confirms. For Meta and TikTok on a Shopify store, the absence of a pixel in the page source is not
evidence of absence — the pixel usually sits in Shopify's server-side web-pixels sandbox, so check
the platform ad libraries instead.
