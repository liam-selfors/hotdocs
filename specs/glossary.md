# Glossary

Canonical vocabulary for this spec corpus. Specs **MUST** use these terms as
defined; a component's own `Definitions` section may only add deltas, never
silently redefine a term here.

Single file by default — see `SPEC_GUIDELINES.md` §3.6 for the (rare,
deliberate, `architecture/`-level) conditions under which it's allowed to
split.

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
