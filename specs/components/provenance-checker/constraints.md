# Provenance Checker — Non-Functional Constraints

- **No network access, no model calls.** Pure local file I/O plus one
  var read — same trust tier as `provenance-writer`.
- **Read-only.** Never writes, modifies, or deletes `.provenance.json`
  or any other file (`R-PROVCHECK-004`).
- **Determinism.** Given the same working-tree content, the same
  supplied `spec_bundle_hash`, and the same `VAR-TRUST-JUDGE-PROVENANCE`
  value, the result MUST be byte-identical.
- **Never a cache-manager client.** This component answers a different
  question ("was this proven correct") from `cache-manager`'s ("has
  this work already been done") and MUST NOT call `cache-manager` to
  answer it — conflating the two is the exact gap this component exists
  to close.
