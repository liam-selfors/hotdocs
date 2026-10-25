# Merge Tracker — Non-Functional Constraints

- **No network access, no model calls.** Pure local file I/O —
  assembling already-produced facts, same posture `provenance-writer`
  already has.
- **Never a gate input.** Nothing under `.hotdocs/` MUST ever be read by
  any component's pass/fail decision (`SPEC_GUIDELINES.md` §1). This
  component writing successfully or not MUST have no bearing on the
  merge's own outcome (`R-TRACK-005`).
- **Append-only, never mutated.** A tracking record, once written, MUST
  NOT be edited or deleted by this component — history is the entire
  value of this data; silently rewriting it would defeat the purpose
  (`R-TRACK-001`).
- **Determinism of assembly, not of the merge itself.** Given the same
  inputs (changed ids, component ids, block reasons, overall outcome, and
  the already-written provenance manifests on disk), the assembled
  `TrackingRecord` MUST be byte-identical — this is a claim about this
  component's own logic, not a claim that two merges of the same spec
  state produce identical records (they won't, if one ran a generation
  model call and the other hit a cache — that's exactly the kind of
  difference this component exists to record, not to normalize away).
- **No retention/eviction policy specified here.** `.hotdocs/tracking/`
  growing without bound over a long-lived local checkout is a real,
  known cost — deliberately left unaddressed in this version, the same
  posture `cache-manager`'s own eviction-policy open question already
  has. Not blocking because this is local, gitignored, disposable data a
  developer can delete at any time with no correctness consequence —
  unlike an unbounded cache, there is no merge behavior that depends on
  old tracking records still being present.
