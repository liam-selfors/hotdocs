# CLI

None (`D91`). This component had its own standalone CLI once
(`hotdocs generate <component-id> --model=...`, just the raw
candidate-producing step); that verb now belongs to
`component-gate-runner`'s full gauntlet (`hotdocs generate`, same
name, different and broader scope) — nobody has a reason to call just
this component's own narrower step directly, so this component no
longer exposes one. `generate()` (`interface/library.md`) is called
only internally now, by `component-gate-runner`.
