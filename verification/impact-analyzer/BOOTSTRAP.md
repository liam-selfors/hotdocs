# Bootstrap Account: `impact-analyzer`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D58`), through two real `generate()`
calls and one real timeout tuning.

**Call 1** timed out twice at `D52`'s 300-second floor; tested directly
with 600s, it completed in 437s. `impact-analyzer` is a meaningfully
larger, more structurally complex component than any built before it —
fixed by raising `ANTHROPIC_TIMEOUT_SECONDS` to 600 (still satisfying
`R-ENDPOINT-004`'s "at least 300 seconds" floor).

**Call 2**, once it completed, produced a well-structured candidate
that never actually compared anything against git history, despite
`R-IMPACT-002`/`003`/`008` requiring detection "relative to the prior
commit" — a git ref nothing in this corpus had ever defined. Confirmed
by direct test against the real repo: `--changed comp-cache-manager`
never propagated to any real dependent. Also found: its output used
the bare slug as `component_id`, contradicting `BlastRadiusReport.md`'s
own example. Neither issue was a candidate mistake alone — both were
real, previously-unspecified corpus gaps (`D64`): "the prior commit"
is now defined as the merge-base with the default branch;
`BlastRadiusReport.md` now states the `comp-<slug>` output format
explicitly. Not swapped in.

**Call 3**, with both fixes in place, correctly implemented real git
`merge-base`/`show`/`ls-tree`-based change detection and the correct
output format — but this component's own hand-written test suite (built
only after this point, covering every `AC-IMPACT-*` criterion against a
real git repo) found a third bug: `R-IMPACT-008`'s `depends_on_
guarantees` narrowing never actually narrowed, because the candidate
parsed a guessed `{component, guarantees}` dict shape instead of the
real flat list of bare `G-<comp>-NNN` strings (confirmed from
`generator`'s own real frontmatter). The real shape was already
documented, in `SPEC_GUIDELINES.md` §2 — which, like every other
guideline-only fix this sequence has found, never reaches a generating
model, since no `SpecBundle` includes it. Fixed by clarifying directly
in `R-IMPACT-008.md` (`D65`). Not swapped in.

**Call 4**, with all three fixes in place, passed all 12 `AC-IMPACT-*`
tests for real — including `AC-IMPACT-010`, specifically designed to
discriminate `merge-base` from `HEAD~1` (a scenario where the two
disagree, so a candidate silently using the wrong ref would be caught).
Swapped in.

The test suite reuses `spec-bundle-assembler`'s own proven lint-clean
synthetic fixture pattern (`comp-foo`/`comp-bar`), wrapped in a real
git repo (`git init`, a baseline commit on `main`, a `feature` branch)
so `R-IMPACT-010`'s merge-base resolution has real history to walk.
