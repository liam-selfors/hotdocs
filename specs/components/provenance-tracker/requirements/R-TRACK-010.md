# R-TRACK-010

**R-TRACK-010** — `check_readiness` (`R-TRACK-009`) MUST additionally
  check every product capability whose `realizes`-set intersects the
  component scope just resolved, through `capability-scenario-verifier`
  (`D89`/`D92`, unreversed by `D93`), never re-deriving its hit/miss
  logic. Unlike the component half this is check-then-run, since
  capability verification never produces source code, only exercises
  what exists. For each such capability, in this order:

  1. call `check_capability_provenance(capability_id, repo_root)`;
  2. if its `hit` is true, that result is the capability's result and
     nothing further is called for it;
  3. if its `hit` is false and `model` is `None`, the capability is not
     ready, with the `not_ready_reasons` entry
     `<capability_id>: needs a fresh run; pass --model`, and nothing
     further is called for it (`D323`): the components are still all
     checked and reported;
  4. otherwise call `run_capability_gates(capability_id, repo_root,
     model, seed, llm_backend)`, passing this function's own three values
     through unchanged (`D174`'s signature) — never
     `run_capability_scenarios`, a different function for a different
     purpose.

  **The `realizes` edge is declared per-component, never per-capability**
  (`D77`, `D122`): scan every `specs/components/*/component.md` for its
  own `realizes:` frontmatter; a product capability's file, under
  `specs/product/<name>.md`, has no `realizes` field to read back.

  `VerifyReport.ready` MUST be `true` if and only if every component in
  scope is ready (`R-TRACK-009`, a sealed one by its sealed manifest)
  **and** every intersecting capability comes back passing — a single
  failing component or capability makes `ready` false, with that item
  named in the report.

  **`capability-scenario-verifier` MUST be loaded lazily, only when at
  least one capability's `realizes`-set intersects the resolved scope**
  (`D98`): a scope with no intersecting capability never loads it.
