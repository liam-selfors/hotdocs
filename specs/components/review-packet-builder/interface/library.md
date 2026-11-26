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

Implements: `specs/architecture/cli-conventions.md`
