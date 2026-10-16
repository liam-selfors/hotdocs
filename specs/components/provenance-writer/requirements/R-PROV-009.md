# R-PROV-009

**R-PROV-009** — When `cache_hit` is `true` (D11), `verification_report`,
  `cross_model_check`, `license_scan`, and `secret_scan` MUST be copied
  verbatim from the matching prior commit's manifest (looked up via
  `cache-manager`'s own key), not recomputed — this is the concrete
  mechanism behind D11's "rollback is a cache-hit" claim, which nothing
  before this component actually implemented.
