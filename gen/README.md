# Generated Code

Regenerable output of the pipeline. Committed on every branch (large binary
assets go through Git LFS). Never hand-edited, with exactly two declared,
tracked exemptions — `sealed` components and file-level pinned overrides.

See `SPEC_GUIDELINES.md` §1 (commit policy) and §9 (exemptions).

## `spec-linter/`

**Hand-authored bootstrap, not real pipeline output** — `generator` doesn't
exist yet. See `verification/spec-linter/BOOTSTRAP.md` for the full, honest
account (what was ambiguous, what was decided, what bugs this caught).
`.provenance.json` in that directory is deliberately filled with
non-pipeline values so this is never later confused with a real cold-regen
artifact.

Everything else fills in once the real `generator` exists.
