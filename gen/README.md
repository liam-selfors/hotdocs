# Generated Code

The tool's own components, one directory per component, named by slug
(`gen/<slug>/`). A project made by `hotdocs init` has its own `gen/` for its
own components and uses these from the tool's checkout (`D199`).

Committed on every branch and never hand-edited: a component is changed by
editing its spec and running `hotdocs generate`, and the result replaces this
directory only after every acceptance criterion passes. The two declared
exemptions, `sealed` components and file-level pinned overrides
(`.overrides.json`), are in `SPEC_GUIDELINES.md` §8.

Five directories are hand-written and tested rather than generated:
`generator` and `llm-endpoint` (each runs through the other, so neither could
be generated first) and `spec-linter`, `graph-query-engine` and
`cache-manager` (built before the generator existed). Everything else here
was produced by `generator` from its component's spec bundle and verified by
`verifier-orchestrator`; the manifest in `verification/<slug>/.provenance.json`
records which spec hash and model produced it.

Each component is a flat module file or a package found by path, not an
installed Python package. `hotdocs-cli` loads a verb's module by file; a
component loads a dependency from `<repo_root>/gen/<slug>/`, falling back to
the same path under the tool root.
