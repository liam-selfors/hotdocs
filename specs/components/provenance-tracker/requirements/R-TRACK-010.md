# R-TRACK-010

**R-TRACK-010** — `check_readiness` (`R-TRACK-009`) MUST additionally
  call `capability-scenario-verifier`'s `run_capability_gates`
  (`D89`/`D92`, unreversed by `D93`) for every product capability whose
  `realizes`-set intersects the component scope just resolved, passing
  the same `model`/`seed`/`llm_backend` through unchanged, never
  re-deriving its hit/miss logic — unlike the component half
  (`R-TRACK-009`), this is check-then-run, not pure read, since
  capability-scenario verification never produces new source code, only
  exercises what already exists, so triggering it from `hotdocs verify`
  costs a developer nothing they wouldn't expect. If any such call would
  be a miss and `model` is `None`, MUST report a usage error rather than
  skip the capability or run it anyway.

  **The literal call, as a worked snippet, not just a name in prose**
  (`D125`): `capability_scenario_verifier.run_capability_gates(capability_id,
  repo_root, judge=judge, test_author=test_author)` — never
  `run_capability_scenarios` (a different function on the same
  dependency, taking a `blast_radius` list, for a different purpose
  entirely — `R-SCENARIO-002`/`interface/library.md`). The two names
  are similar enough that prose alone naming the right one was not
  reliably sufficient.

  **The `realizes` edge is declared per-component, never per-capability**
  (`D77`, `D122`): compute it by scanning every
  `specs/components/*/component.md` for its own `realizes:` frontmatter
  field (a component declares which `P-id`(s) it realizes); a product
  capability's own file, under `specs/product/<name>.md` — never a
  nonexistent `specs/capabilities/`— has no `realizes` field of its own
  to read back. Mirrors `capability-scenario-verifier`'s own internal
  `_collect_realizes_edges`, never re-derived independently or guessed.

  `VerifyReport.ready` MUST be `true` if and only if every component in
  scope is a provenance hit with a passing `verification_report` and no
  blocking scan result, **and** every intersecting capability comes back
  passing from `run_capability_gates` — a single component or capability
  failing either check makes `ready` false, with that item named in the
  report, same as `R-TRACK-009`'s per-component detail.

  **`capability-scenario-verifier` MUST be loaded (imported/resolved)
  lazily, only when at least one product capability's `realizes`-set
  actually intersects the resolved scope, never eagerly alongside
  `provenance-checker` as shared setup** (`D98`, same posture
  `R-TRACK-009` now states for `impact-analyzer`): a scope with no
  intersecting capability at all never loads this dependency's module.

