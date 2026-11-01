# R-PROVCHECK-001

**R-PROVCHECK-001** — Given a component id, its current
  `spec_bundle_hash`, the current `gate_versions` map, and a repo root,
  MUST read `gen/<component>/.provenance.json` as it currently sits in
  the working tree (not from any store), and compare both its own
  `spec_bundle_hash` field and every entry of its own `gate_versions`
  map against the supplied ones — a hit requires every value to match
  exactly, not just `spec_bundle_hash`. `check_provenance` never computes
  either value itself — both are always caller-supplied, obtained from
  `current_provenance_key` (`R-PROVCHECK-005`), the same
  "gate version is part of the key, not metadata checked after" rule
  `R-CACHE-005` already established for a different store, applied
  here for the same reason: a stale manifest must not paper over a
  gate's own detection logic having since improved.

