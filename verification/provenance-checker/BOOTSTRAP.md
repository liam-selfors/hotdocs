# Bootstrap Account: `provenance-checker`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D42`), through three real retries.

**Retry 1** produced a well-reasoned 3-file candidate that built
`gen/<component_id>/.provenance.json` directly from the caller-supplied
`component_id`, never stripping its `comp-` prefix — a real,
previously-undocumented corpus-wide gap (`D45`): nothing anywhere
stated that `gen/<component>/`-shaped paths use the bare slug, not the
full `comp-<slug>` id. Confirmed by direct test: a real hit was
reported as a miss. Fixed by documenting the convention in
`glossary.md` (part of every real `SpecBundle`); not swapped in.

**Retry 2**, with that fix in place, produced a candidate that
correctly stripped the prefix but laid its output out as
`src/provenance_checker/*.py` plus a `pyproject.toml` — a layout
`spec-bundle-assembler`'s `dependency_usage` (`R-ASSEMBLE-011`) never
looks for (only a flat module or a top-level package directly under
`gen/<slug>/`). Also caught a real process mistake on the operator's
own side: the fix (new `R-GEN-015`, a `generator.py` prompt addition)
bumped `PROMPT_VERSION` but not `GATE_VERSION`, so a same-hash retry
made right after landing the fix got a stale cache hit replaying the
pre-fix candidate instead of a fresh call (`D46`'s own account).
Neither candidate was swapped in.

**Retry 3**, with both fixes (and the cache-key fix) in place,
produced a correctly-laid-out top-level package that resolves the
`comp-` prefix correctly, independently reinventing the exact pattern
`glossary.md`'s new entry describes — its own code comments cite that
entry and the prior bug by name. All 8 `AC-PROVCHECK-*` criteria pass
for real against this candidate (9 tests — one criterion,
`AC-PROVCHECK-005`, is covered by two tests: the explicit-`true` case
and the absent-var-defaults-to-`true` case, both real behaviors worth
distinguishing).

One interface deviation, judged acceptable: `check_provenance` gained
an optional `trust_judge_provenance: bool | None = None` keyword
parameter beyond `interface/library.md`'s exact signature, falling
back to environment-variable resolution when omitted (matching the
spec's documented default exactly). Every required positional
parameter matches; the addition only ever narrows nothing a caller
already relies on.
