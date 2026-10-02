# Bootstrap Account: `spec-linter`

This is the honest record the exercise asked for: `gen/spec-linter/` and
`verification/spec-linter/` were built by hand, standing in for two
components that don't exist yet — `generator` (there is no cold-regen
pipeline to have produced `gen/spec-linter/` the normal way) and
`criterion-compiler` (there is no deterministic Gherkin compiler to have
turned `acceptance.md`'s Given/When/Then blocks into
`verification/spec-linter/test_lint_rules.py` the normal way). Both
stand-ins are one-time bootstrap exceptions, not a new pattern — flagged
explicitly here rather than left implicit.

**Language:** Python 3, no external dependencies (frontmatter is hand-parsed
rather than using PyYAML). A real generator-produced implementation would
likely reach for PyYAML; the zero-dependency choice here is specifically to
keep this bootstrap trivially runnable. Tests use `pytest`, installed into an
isolated venv for the run, not added to the repo.

## The three pre-existing open questions, resolved

1. **RFC 2119 keyword list.** Resolved: `MUST`, `MUST NOT`, `SHOULD`,
   `SHOULD NOT`, `MAY` — the curated subset, not the full RFC 2119 set. This
   didn't actually need to be an open question: `SPEC_GUIDELINES.md`'s own
   opening paragraph already states exactly this ("Keywords MUST, MUST NOT,
   SHOULD, SHOULD NOT, and MAY are used per RFC 2119"). It was answerable by
   cross-referencing a document already in hand.
2. **Cycle-detection algorithm.** Resolved: standard DFS white/gray/black
   marking. There was no real ambiguity here — any correct algorithm works,
   as the spec said.
3. **Pre- vs. post-compilation size counting.** Resolved: pre-compilation.
   Turns out the question was slightly moot once actually implemented —
   compiled test scaffolding doesn't exist at lint time (there's no
   `criterion-compiler` run yet to have produced it), so there is nothing to
   count "post-compilation" at the point the linter runs regardless.

## Gaps found that weren't already flagged

- **Rule-boundary ambiguity in `SPEC_GUIDELINES.md` §2.** The frontmatter
  table conflates unconditionally-required fields (`id`/`title`/`status`/
  `owners`) with conditionally-required ones (`realizes` unless sealed,
  `source_path` when sealed, `last_ratified_commit` when ratified) under one
  table with one "Required" column. `R-LINT-001` ended up only covering the
  unconditional four, deferring the rest to `R-LINT-002`/`005`/`006` — a
  split that works but isn't something `SPEC_GUIDELINES.md` actually states.
- **Which file in a component bundle carries which frontmatter field is
  never specified.** `depends_on`/`realizes`/`uses_var`/`sealed`/
  `source_path`/`model_pin`/the two toggles — `SPEC_GUIDELINES.md` describes
  these as component-level fields without saying that, by consistent
  example, only `spec.md` carries them (`interface.md`/`acceptance.md`/
  `constraints.md` carry just the four universal fields). Implemented
  against the convention actually used in every example file written so far;
  worth stating explicitly in `SPEC_GUIDELINES.md` rather than leaving it
  inferable.
- **`specs/vars/` field location is ambiguous and arguably wrong.**
  `SPEC_GUIDELINES.md` §3.3 lists `required`/`type`/`sensitivity`/
  `description`/`example`/`default` as "fields" without saying frontmatter
  or body. Every actual example file puts them as body bullets
  (`- **sensitivity:** secret`). `R-LINT-013` had to parse body text instead
  of reusing the frontmatter path every other rule uses. **Recommend**:
  move these into frontmatter for consistency with every other doc type —
  it would also make `R-LINT-013` trivial rather than bespoke.
- **No documented way to tell a governed spec from scaffolding.** Every
  `specs/` subdirectory has a `README.md` placeholder (from the repo
  scaffold) sitting next to real specs. `SPEC_GUIDELINES.md` never says how
  the linter should tell them apart. Implemented by filename convention
  (component dirs: only the four named files are specs; elsewhere: any
  `.md` that isn't `README.md`). A different implementer could reasonably
  have chosen differently — this should be a documented rule, not an
  inference.
- **`R-LINT-011` may be mis-assigned `kind: compiled`.** "Redefines a term
  ... rather than only adding a delta" asks for a judgment about *meaning*,
  not structure. What's implemented is a conservative heuristic (flag if the
  glossary term's exact name reappears as a defined entry in `Definitions`
  at all) — it will false-positive on a legitimate elaboration that happens
  to restate the term's name, and false-negative on a sneaky redefinition
  that avoids doing so. This looks like a real candidate for `llm-judge`
  instead of `compiled` — which would mean `AC-LINT-011` was assigned the
  wrong `kind` when `acceptance.md` was first written, a direct miss of D5's
  own guidance by the same component that's supposed to demonstrate it.
- **No canonical way to count "interface surface elements."**
  `SPEC_GUIDELINES.md`'s D2 size-cap table names this dimension but
  `interface.md` is free-form prose, not a machine-readable schema. What's
  implemented (counting top-level backtick-led bullets) is a rough
  approximation, not a specified algorithm. Either `interface.md` needs a
  more structured convention (e.g., a single fenced block listing just
  signatures) or this dimension has to stay inherently approximate — worth
  deciding rather than leaving implicit.

## A bug the bootstrap itself caught, worth generalizing

The first implementation of the RFC-2119-keyword check only looked at the
single physical line carrying the `**R-id**` marker. Every one of the 14
hand-built `AC-LINT-*` fixtures happened to use single-line requirement text,
so the full test suite passed with this bug still in place. It was only
caught by running the linter against this repository's **real**,
independently-authored corpus — two sibling components written by other
agents in parallel used the normal multi-sentence, line-wrapped requirement
style, and the bug produced eight false-positive failures against clean,
correct specs. Fixed (requirement text is now collected as a full block, to
the next bullet or section end, not a single line).

**The generalizable lesson, not just the bug:** a linter/compiler-shaped
component's acceptance criteria, however thorough, were hand-built as
single-violation fixtures — and that made them systematically blind to a
whole class of bug (anything only visible across multiple lines of real,
organically-written content). Validating a `compiled`-kind component against
real, independently-produced spec content caught something a complete
fixture suite did not. Worth considering as a standing practice, not a
one-off: this component's acceptance criteria could use a companion
requirement along the lines of "MUST also be validated against the corpus's
real spec content, not only synthetic fixtures" — currently nothing in
`spec.md`/`acceptance.md` asks for that.

## What was *not* ambiguous

Worth stating plainly, since the point of this exercise cuts both ways:
`interface.md`'s CLI contract (flags, exit codes) and the `LintReport` JSON
schema were sufficient to implement from directly, with no guessing. The
14 `R-LINT-*` requirements and their 1:1 covering criteria were, with the
exceptions above, implementable without needing to invent behavior the spec
didn't describe.

## Follow-up round: resolving what this bootstrap flagged as open

Two things this report originally flagged — "no canonical algorithm for
interface surface elements" and "R-LINT-011 may be mis-assigned `compiled`"
— were resolved afterward, against this same real implementation:

- **`_count_interface_surface` replaced the markdown-bullet heuristic**
  (which happened to count CLI flag descriptions, not actual surface
  elements) with a concrete algorithm: one per CLI invocation line, one per
  `Library` function signature, one per `## Data: ...` heading. Verified
  against this repo's four real `interface.md` files
  (`test_interface_surface_counting.py`) — `spec-linter`/`impact-analyzer`/
  `criterion-compiler` = 3 each, `cache-manager` = 6 (its `get`/`put` and
  `inspect`/`stats` pairs are two signatures each in one fenced block, which
  is exactly why "one per code block" would have undercounted it).
- **R-LINT-011 split into two requirements**, matching D5's own guidance
  about when `llm-judge` is warranted: R-LINT-011 stays `compiled` but now
  only fires on a *near-verbatim* restatement (token-overlap ratio ≥ 0.8) of
  the glossary's definition — genuinely mechanical, no judgment. A new
  R-LINT-015 (`llm-judge`) covers the case R-LINT-011 structurally cannot:
  different wording that still substantively *conflicts* with the glossary's
  meaning. With no model configured, R-LINT-015 reports `severity: skipped`
  — never silently passing, never crashing — the same posture D10
  established for model-pin availability, applied a third time. A
  regression test (`test_ac_lint_011_old_fixture_now_routes_to_015_not_011`)
  confirms this bootstrap's *own original* R-LINT-011 fixture — which
  happened to pass under the old, too-broad heuristic — now correctly
  routes to R-LINT-015 instead.

No model-call integration exists in this bootstrap (`rule_llm_judge_
glossary_conflict` takes an injectable `judge` callable, tested with a mock
in `test_ac_lint_015_conflict_detected_with_judge_configured`) — wiring a
real model in is explicitly out of scope for a hand-authored CLI prototype,
and would have been dishonest about what was actually validated here.
