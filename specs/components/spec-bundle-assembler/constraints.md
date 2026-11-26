# Spec Bundle Assembler — Non-Functional Constraints

- **Performance.** Assembling one component's bundle MUST complete in well
  under 1 second on reference hardware.
- **No network access, no model calls.** Pure file I/O and hashing.
- **Isolation between modes.** A `cold`-mode bundle's non-`hint_code` fields
  MUST be identical to what a `hint`-mode call for the same component would
  produce — `hint_code` is strictly additive, never a substitute for any
  cold-mode field.
