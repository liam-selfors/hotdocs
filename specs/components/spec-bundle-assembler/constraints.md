# Spec Bundle Assembler — Non-Functional Constraints

- **Determinism.** Same corpus content, byte-for-byte, MUST always produce
  the same `SpecBundle`. Required for `spec_bundle_hash` to be a valid
  cache key (D11/D13).
- **Performance.** Assembling one component's bundle MUST complete in well
  under 1 second on reference hardware — this runs on every generation call
  (canonical and every hint-mode preview), so it must stay negligible
  relative to the model call it precedes.
- **No network access, no model calls.** Pure file I/O and hashing.
- **Isolation between modes.** A `cold`-mode bundle's non-`hint_code` fields
  MUST be identical to what a `hint`-mode call for the same component would
  produce — `hint_code` is strictly additive, never a substitute for any
  cold-mode field.
