# R-PROVCHECK-001

**R-PROVCHECK-001** — Given a component id, its current
  `spec_bundle_hash`, the current `gate_versions` map, and a repo root,
  MUST read `gen/<component>/.provenance.json` as it currently sits in
  the working tree (not from any store), and compare both its own
  `spec_bundle_hash` field and every entry of its own `gate_versions`
  map against the supplied ones — a hit requires every value to match
  exactly, not just `spec_bundle_hash`. `check_provenance` never computes
  either value itself — both are always caller-supplied, obtained from
  `current_provenance_key` (`R-PROVCHECK-005`), so a stale manifest
  never papers over a gate that has since improved (`R-CACHE-005`).

