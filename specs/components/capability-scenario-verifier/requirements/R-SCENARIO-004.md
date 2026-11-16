# R-SCENARIO-004

**R-SCENARIO-004** — MUST expose `check_capability_provenance(capability_id,
  repo_root)` and `run_capability_gates(capability_id, repo_root,
  model=None, seed=0, llm_backend=None)`, each returning a
  `CapabilityProvenanceCheckResult` (`D89`, `D92`, `D174`). An unknown
  `capability_id` — no `specs/product/*.md` whose frontmatter `id` is it
  — raises `UnknownCapabilityError` from both.

  `check_capability_provenance` is a pure read. It returns `hit` `true`
  iff the committed record (`R-SCENARIO-006`) is a readable JSON object
  whose `gate_version` and `content_hash` both equal the current ones,
  and then carries the record's `capability_scenario_report`. Any other
  case — no record, an unreadable one, a stale one — is `hit` `false`
  with the report `null`. A recorded **failing** report is still a hit:
  fixing the cause changes the content, and so the key.

  `run_capability_gates` checks first. On a hit it returns that result
  unchanged: no dependency loaded, no scenario run, nothing written,
  and no `model` needed. On a miss with `model` `None` it raises
  `ModelRequiredError` before loading, running, or writing anything.
  Otherwise it runs the capability's scenarios (`R-SCENARIO-001`) with
  the callables `R-SCENARIO-007` and `R-SCENARIO-008` build, writes the
  fresh record, and returns `hit` `false` with the fresh report for just
  this capability. A failing run is recorded exactly like a passing one.
