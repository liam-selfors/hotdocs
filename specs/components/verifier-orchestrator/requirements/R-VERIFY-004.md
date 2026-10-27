# R-VERIFY-004

**R-VERIFY-004** — This component MUST perform the interface drift check:
  every callable `interface/library.md`/`interface/cli.md` documents MUST
  exist in `gen/<component>/` with a matching parameter list; any missing
  callable or parameter mismatch MUST be recorded as a hard failure.

  **One-directional, not set equality** (`D84`) — a module defining
  additional public names `interface/` never documented (a helper
  class, a return-type dataclass, an internal-but-unprefixed function)
  MUST NOT itself count as drift. Those names are either genuinely
  internal (naming them `interface/`-worthy was simply never asked for)
  or already covered by `interface/data/`'s own, separate contract —
  this check's job is only "does the documented interface still work,"
  never "does nothing else exist."
