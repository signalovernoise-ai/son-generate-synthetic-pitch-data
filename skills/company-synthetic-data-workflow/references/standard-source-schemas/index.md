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
- `triple-whale.md`
- `ordergroove.md`
- `recharge.md`
- `gorgias.md`
- `custom-postgres.md`

Pick **one** system per domain per company, backed by evidence:

- subscriptions: `recharge.md` or `ordergroove.md`
- campaign / lifecycle: `klaviyo.md` or `bloomreach.md`
- support: `gorgias.md` or `zendesk.md`
