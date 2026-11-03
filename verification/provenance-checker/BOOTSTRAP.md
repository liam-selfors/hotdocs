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

## `D163`: `current_provenance_key` and CLI coverage

Regenerated to own the one definition of a provenance key
(`R-PROVCHECK-005`): `spec-bundle-assembler`'s cold-mode bundle hash,
plus each verifying gate's version, read without running any gate. The
CLI is now covered (`R-PROVCHECK-006`, `D162`); writing that
requirement exposed that the previous CLI accepted only a bare hex
`--spec-bundle-hash`, rejecting every real `sha256:`-prefixed hash.
Every criterion's fixture paths were also corrected from
`gen/comp-foo/` to `gen/foo/`, per the glossary. Landed on the first
round at 10 of 10, `mutation_score=0.91`, now a flat module rather than
a package. Against this repository, `current_provenance_key` returns
the same hash `assemble` does and all five gate versions; the
hand-maintained suite still passes.

## `D170`: sealed keys and the sealed manifest check

Regenerated to add the sealed counterpart of the provenance key:
`current_sealed_key` (the one test of whether a component is sealed,
and its owners, source hash, and verifier version) and
`check_sealed_provenance` (is the sealed manifest valid and current;
`R-PROVCHECK-007`/`008`). Five rounds, landing at 13 of 13 criteria,
`mutation_score=0.91`. The new requirements passed from the second
round; the rest was spec precision:

- Two criteria snapshotted the repository to prove the check wrote
  nothing and tripped on the `__pycache__` that importing a faked
  dependency creates (the third time this session). The criterion now
  excludes it by name.
- A miss returned `null` for every manifest-derived field, where the
  data document said they were copied "when the manifest is valid". The
  candidate had the better reading — a manifest that is not a current,
  passing hit is not evidence — and the document now says so.
- `AC-PROVCHECK-004`/`005` never set `VAR_TRUST_JUDGE_PROVENANCE`, so a
  test assumed absent meant false; the declaration makes absent mean
  true. Both now name the environment variable.
- Mutation testing, with every criterion passing, found the manifest
  validator's per-field type checks untested (0.74): the new
  `AC-PROVCHECK-013` changes one field at a time through wrong types and
  malformed values.

The older hand-written `test_provenance_checker.py` read results as
attributes (`result.hit`); the candidate, like its dependents, treats a
result as a dict or an object, so the suite now reads fields through a
dual-access helper rather than being deleted. 99 of 99 pass. Against the
real repository the checker returns `criterion-compiler`'s key,
`None` for every other component, and `manifest_missing` until a
manifest exists.
