# R-PACKET-005

**R-PACKET-005** — License- and secret-scan results MUST appear as their
  own explicit section, even when both are clean — never folded into a
  generic results blob where a flag could be missed — every flag stays
  strictly tracked and communicated.

  `compliance_flags.license_scan` is a `{"component_id", "result"}`
  entry for exactly the components whose per-component `license_scan`
  value's own `blocked` field (verbatim from `license-scanner`'s
  `LicenseScanResult.blocked`, flowing through `provenance-tracker`
  unmodified) is `true` — `[]` when none are. `secret_scan` is `[]`
  unless `VerifyReport.secret_scan`, the one fresh repository scan, has
  `flagged` true; it is then exactly `[{"component_id": null, "result":
  <that scan>}]`, since that scan belongs to no component; absent or
  `null`, it is `[]`. A component's
  stored `secret_scan` is never read (`D371`). Never a heuristic guess across other
  possible key names — `blocked`/`flagged` are the one real signal.
