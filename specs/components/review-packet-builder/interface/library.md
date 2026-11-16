# Library

```
build_review_packet(changed_ids: list[str], repo_root: Path) -> ReviewPacket
```

`changed_ids` is the caller's own authoritative list of every spec id
that changed in this PR (component ids, `R-id`s, `AC-id`s, capability
ids) — never independently rediscovered from git by this component.
`changed_requirements` (`R-PACKET-002`) is simply its `R-id`-shaped
subset.

`provenance-tracker` is one flat module file,
`gen/provenance-tracker/provenance_tracker.py`, loaded per `R-PACKET-013`.

## Test fixtures

Unless a criterion says otherwise, every criterion builds `repo_root`
as a git repository with at least one commit and a `provenance-tracker`
stand-in at `<repo_root>/gen/provenance-tracker/provenance_tracker.py`
in place of the real one (the real one calls `impact-analyzer`, which
rejects a spec id the corpus does not hold). The stand-in defines
`check_readiness(repo_root, changed_ids=None, model=None, seed=0,
llm_backend=None)` returning a `VerifyReport`-shaped dict written as a
Python literal (`True`, `False`, `None`, never JSON spelling, never
`repr` of an already-`repr`'d value) and
`last_requirement_failures(component_id, repo_root)` returning `[]`.
Each criterion states what that dict reports; a spec id such as
`R-FOO-002` exists only in the fixture's files and that dict.

Implements: `specs/architecture/cli-conventions.md`
