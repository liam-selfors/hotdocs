# Glossary

Canonical vocabulary for this spec corpus. Specs **MUST** use these terms as
defined; a component's own `Definitions` section may only add deltas, never
silently redefine a term here.

Single file by default — see `SPEC_GUIDELINES.md` §3.6 for the (rare,
deliberate, `architecture/`-level) conditions under which it's allowed to
split.

- **Component id / component slug** — a component's id, as carried in
  `component.md`'s frontmatter and `SpecBundle.component_id`, is always
  `comp-<slug>` (e.g. `comp-cache-manager`). The bare `<slug>` (`comp-`
  stripped) is the directory name used everywhere a path is built from
  it — `specs/components/<slug>/`, `gen/<slug>/`,
  `verification/<slug>/` — never the full `comp-<slug>` id. This was
  never written down anywhere before `D61`, despite being load-bearing
  for every component that resolves a `gen/<component>/`-shaped path
  from a `component_id` it was handed — each one independently
  reimplemented the same strip-the-prefix logic, and a real generated
  candidate (`provenance-checker`) got it wrong for exactly that
  reason, silently treating every real hit as a miss.
- **Spec bundle** — the full set of files a generation or verification step
  needs for one component: `component.md` + `requirements/` + `interface/` +
  `constraints.md` + depended-upon components' `interface/` directories +
  referenced `specs/vars/` declarations + `glossary.md` (deliberately
  excluding `acceptance/`, to avoid overfitting to its own tests — D15).
- **Unit file** — a file under a component's `requirements/`, `interface/`
  (including `interface/data/`), or `acceptance/` directory, holding exactly
  one addressable thing (one requirement, one interface section, one
  criterion), identified by its filename, with no frontmatter of its own
  (D15).
- **Blast radius** — the minimal set of components `impact-analyzer`
  determines need regeneration/re-verification for a given spec change.
- **Gate** — one verification step in the pipeline (lint, a `kind`-specific
  acceptance check, license scan, secret scan, non-functional checks). A
  merge requires every applicable gate to pass.
- **Cache hit** — a merge whose spec bundle hash exactly matches an
  already-verified prior state; restores prior artifacts instead of
  re-running gates (D11).
- **Provenance manifest** — the `.provenance.json` file recording exactly how
  a generated artifact was produced (D7).
- **Sealed component** — a component explicitly exempted from the cold-regen
  invariant, with its real code at `source_path` instead of under `gen/`.
  Used both for legacy code being wrapped and for permanently-hand-maintained
  trust infrastructure (e.g. `criterion-compiler`) — not legacy debt alone.
- **Pinned override** — the file-granularity version of the same exemption,
  declared in `gen/<component>/.overrides.json`.
- **Criterion test filename** — the deterministic filename a criterion's
  executable test file is always written/read under, for both
  `kind: compiled` (`criterion-compiler`) and `kind: generated-test`
  (`test-author`) output: `test_<criterion_id, lowercased, '-' -> '_'>.py`
  (e.g. `AC-FOO-003` → `test_ac_foo_003.py`), directly under
  `verification/<component>/<compiled|generated-test>/` — no further
  nesting, no content hash or other suffix. Both producers already used
  this exact formula independently; `verifier-orchestrator`, the
  dependent that must *check for* a `generated-test` file before
  deciding whether to dispatch to `test_author` (`R-VERIFY-002`), is
  the first consumer, and this was never written down anywhere as a
  shared contract before `D80` — two independent real candidates each
  invented a different, incompatible filename/location scheme for the
  same check, since nothing bundle-visible stated the formula as a
  rule rather than one illustrative JSON example.
