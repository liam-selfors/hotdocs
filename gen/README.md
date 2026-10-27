# Generated Code

Regenerable output of the pipeline. Committed on every branch (large binary
assets go through Git LFS). Never hand-edited, with exactly two declared,
tracked exemptions — `sealed` components and file-level pinned overrides.

See `SPEC_GUIDELINES.md` §1 (commit policy) and §8 (exemptions).

## Real code exists for seven components so far

Two distinct categories, not one undifferentiated "bootstrap" bucket:

**Hand-authored bootstrap exceptions** — stood in for a real `generator`
before one existed, each documented in its own `verification/<component>/
BOOTSTRAP.md`:

- `spec-linter/` — the first, and the tool every spec change in this repo
  is actually re-validated against before it's committed.
- `graph-query-engine/` — the shared DuckDB query layer several other
  components (including `spec-linter`'s own graph-shaped rules) query
  instead of each writing independent frontmatter parsing.
- `cache-manager/`, `spec-bundle-assembler/` — `generator`'s own
  dependencies; temporary exceptions, not permanent ones.
- `llm-endpoint/` — a *permanent* exception: it's the component every real
  generation call dispatches through, so nothing could ever cold-regenerate
  it first, even once a real `generator` exists.
- `generator/` — also permanent, for the same reason in reverse: it's the
  component that does the cold-regenerating.

**Really generated — produced by the real `generator`, not hand-written:**

- `corpus-graph-builder/` — cold-generated once, from a mock-free, fully
  real `generator`/`llm-endpoint`/`cache-manager`/`spec-bundle-assembler`
  chain.
- `llm-endpoint/` itself, *twice over* — the real `generator`, dispatching
  through a real (then hand-written) `llm-endpoint`, cold-regenerated
  `llm-endpoint` from its own current spec, then again after two
  spec corrections a real failure surfaced: a too-short timeout bound and
  a missing structural tool-isolation requirement (`D34`/`D35`). Each
  result replaced the prior version only after passing every one of its
  own acceptance criteria — not because a generation attempt merely
  completed.

A `generator`-regenerating-itself attempt was also made (the deepest
self-hosting case) — it produced a plausible five-file candidate that
failed to import (an assumed dependency-module layout that didn't match
`cache-manager`'s real one) and was correctly **not** swapped in
(`D46`). `gen/generator/generator.py` is still the original hand-written
file. See `notes/backlog.md` for the generalizable gap this exposed.

Everything else under `specs/components/` is fully specced but has no
real code yet — most of it genuinely needs a model call this corpus has
no automated pipeline for yet (only manually-orchestrated `generate()`
calls made during this methodology's own bring-up).
