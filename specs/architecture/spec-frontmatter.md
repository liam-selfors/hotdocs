---
id: arch-spec-frontmatter
title: Spec Frontmatter
status: draft
owners: [pipeline-team]
depends_on: []
---

# Spec Frontmatter

The frontmatter rules every spec file follows, moved here from
`SPEC_GUIDELINES.md` so a component that checks them reads only these
(`D381`).

## Where frontmatter lives

Frontmatter lives in exactly one place per component: **`component.md`**,
the root file. Every other file in a component — each `requirements/R-*.md`,
each `interface/cli.md` / `interface/library.md` / `interface/data/*.md`,
each `acceptance/AC-*.md`, and `constraints.md` — carries **no frontmatter
at all**. A unit file's identity is its filename and its position in the
directory tree.

A product capability (`specs/product/<name>.md`), an architecture doc
(`specs/architecture/<name>.md`), a var declaration (`specs/vars/<name>.md`),
and a decision record (`specs/decisions/<id>.md`) each remain one flat file
and carry the full field set below, same as `component.md` does for a
component (minus the component-only fields — a product capability has no
`sealed`, for instance). `specs/glossary.md` has no frontmatter at all.

## Fields

"Required" below is one of: **always** (every instance of this field is
mandatory), **never** (optional everywhere), or a stated **condition**
(mandatory only when the condition holds, forbidden otherwise — not merely
optional).

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | always | Stable identifier for the whole spec document (`component.md`, a product capability, etc.). A unit file's own id is its filename (e.g. `R-FOO-001.md`), not a frontmatter field. |
| `title` | always | Human-readable name. |
| `status` | always | `draft` \| `ratified` \| `deprecated`. |
| `owners` | always | Who (human or team) is accountable for this spec. |
| `depends_on` | never (optional) | List of spec ids this one requires. Forms the dependency graph (D2). **(component `component.md` only)** |
| `realizes` | condition: required unless `sealed: true` | List of `P-<id>`s this component contributes to. (D8) **(component `component.md` only)** |
| `uses_var` | never (optional) | List of `VAR-<id>`s this component reads from `specs/vars/`. (D12) **(component `component.md` only)** |
| `assets` | never (optional) | List of `<kind>:<path>` strings: a component's non-Python generated files, each at `gen/<slug>/<path>`. See `specs/architecture/asset-kinds.md`. (D343) **(component `component.md` only)** |
| `drivers` | never (optional) | One-line list of test driver names a component's or capability's criteria use. See `specs/architecture/test-drivers.md`. (D373) **(component `component.md` and capability files only)** |
| `depends_on_guarantees` | never (optional) | List of `G-<comp>-NNN` ids — a **strictly opt-in narrowing** of which of a dependency's `interface/guarantees/` entries this component actually relies on. (D2) **(component `component.md` only)** |
| `supersedes` | never (optional) | Prior spec id this one replaces. |
| `builds_on` | never (optional) | List of prior `D<N>`s this decision's reasoning depends on, without replacing any of them. **(decision record only)** |
| `model_pin` | never (optional); **inapplicable when `sealed: true`** | Per-spec override of the repo-wide canonical model. **MUST** be omitted (not filled with a placeholder) on a sealed component — there is no generation to pin. **(component `component.md` only)** |
| `sealed` | never (optional), default `false` | Legacy-perimeter escape hatch, and the mechanism for a permanently hand-maintained trust anchor. See `SPEC_GUIDELINES.md` §8. (D1/D8) **(component `component.md` only)** |
| `source_path` | condition: required when `sealed: true`, forbidden otherwise | Where the actual, hand-maintained code lives. **MUST NOT** point under `gen/`. **(component `component.md` only)** |
| `last_ratified_commit` | condition: required when `status: ratified` | Commit hash of the ratifying merge. |

## Rules

- A spec **MUST NOT** be `status: ratified` while it has any non-empty `Open
  questions` section.
- `depends_on` **MUST** form an acyclic graph across the whole corpus.
- Every `depends_on`, `realizes`, and `uses_var` reference **MUST** resolve to
  a real, existing spec id. Dangling references are a hard lint failure.
- Every `depends_on_guarantees` entry **MUST** resolve to a real `G-<comp>-NNN`
  id, **and** that id's owning component **MUST** already be listed in this
  component's own `depends_on`. (D2)
- `sealed: true` **MUST** carry a `source_path`; `sealed: false` or absent
  **MUST NOT** carry one.
- Every `assets` entry **MUST** be `<kind>:<path>` with a relative, `/`-separated
  `path` free of `..` and not ending in `.py`, and `<kind>` **MUST** have a
  definition with all seven sections (`specs/architecture/asset-kinds.md`).
- Every `drivers` item **MUST** be a driver name with a definition or an
  adapter (`specs/architecture/test-drivers.md`).
- A unit file under `requirements/`, `interface/`, or `acceptance/`, or
  `constraints.md`, **MUST NOT** carry any frontmatter block at all. Finding
  one is a hard lint failure.

## Var declarations

A var declaration (`specs/vars/<name>.md`) declares one configuration
parameter. Its frontmatter is just `id` / `title` / `status` / `owners`;
its own fields — `name`, `required` \| `optional`, `type` (`string` \|
`url` \| `connection-string` \| `secret-ref` \| `integer` \| `enum` \|
…), `description`, `sensitivity` (`secret` \| `non-secret`), and
`example`/`default` — live in the document **body**, as bullets. (D12)

- There **MUST NOT** be a `value` field anywhere in this schema. The field
  does not exist.
- A declaration with `sensitivity: secret` **MUST NOT** carry an `example` or
  `default` field.
- A component that reads this variable **MUST** reference it via `uses_var`,
  never redefine its meaning locally.
