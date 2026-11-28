---
id: arch-spec-layout
title: Spec Layout
status: draft
owners: [pipeline-team]
depends_on: []
---

# Spec Layout

Where each spec file lives, which files are governed, and the sections
and units a product capability and a component hold, moved here from
`SPEC_GUIDELINES.md` so a component that checks them reads only these
(`D381`).

## Keywords

Normative statements use the keywords **MUST**, **MUST NOT**, **SHOULD**,
**SHOULD NOT**, and **MAY**, per RFC 2119.

## The `specs/` tree

```
specs/
  product/            # capabilities (P-id) + capability end-to-end scenarios
  architecture/        # component decomposition, dependency graph ownership
  vars/                # env/config parameter declarations (VAR-id) — never values
  components/
    <component>/
      component.md      # root: frontmatter + Purpose/Rationale/Scope/
                         # Definitions/Open questions/Change log +
                         # pointers to the below (Rationale optional, D21)
      requirements/
        R-<comp>-NNN.md  # one Behavior requirement each
      interface/
        cli.md           # CLI contract
        library.md       # library/function contract
        data/
          <TypeName>.md   # one schema/type each
        guarantees/
          G-<comp>-NNN.md # one behavioral/non-functional guarantee each,
                          # that a *dependent* may rely on (D2) — optional,
                          # like cli.md/library.md
      acceptance/
        AC-<comp>-NNN.md  # one acceptance criterion each
      constraints.md      # non-functional requirements (one file)
  decisions/           # ADR-style, append-only, immutable once ratified
  glossary.md          # canonical vocabulary
```

## The governed set

A `README.md` anywhere under `specs/` is non-normative scaffolding, not a
governed spec — the linter and every other tool **MUST** skip it. The
governed set under a component directory is exactly: `component.md`;
every file under `requirements/`, `interface/` (including
`interface/data/`), and `acceptance/`; and `constraints.md`. Elsewhere:
any other named `.md` file directly under `specs/product/`,
`specs/architecture/`, `specs/vars/`, or `specs/decisions/`; and
`specs/glossary.md`.

## Product capability

A product capability (`specs/product/<name>.md`) declares a capability
with a stable `P-<id>`. Body: Purpose, Scope, and one or more
Given/When/Then capability scenarios (in the format of
`specs/architecture/acceptance-criteria.md`) exercised **black-box
against the whole assembled system** — never against one component in
isolation. (D8)

## Component

A component (`specs/components/<name>/`) is one root file plus three
unit directories plus one flat file.

**`component.md`** — the root. Carries the frontmatter
(`specs/architecture/spec-frontmatter.md`) and this fixed section order:

| Section | Rule |
| --- | --- |
| Purpose | One paragraph: what this unit does and why it exists — **dependent-safe** (D21): no decision citations (`D<N>`), no historical justification, no cross-references to how this design was arrived at. |
| Rationale | Decision citations, historical justification, cross-references to the discussion that produced this design. **Internal only** — never included in anything assembled for a dependent. Optional: a component MAY omit this section entirely rather than leave it empty. |
| Scope | Explicit in-scope / out-of-scope bullets. |
| Definitions | Only deltas from `glossary.md`. |
| Behavior | Pointer: "See `requirements/`." |
| Interfaces | Pointer: "See `interface/`." |
| Data | Pointer: "See `interface/data/`." |
| Acceptance criteria | Pointer: "See `acceptance/`." |
| Non-functional constraints | Pointer: "See `constraints.md`." |
| Open questions | **MUST** be empty when `status: ratified`. |
| Change log | Human-readable history. |

**`requirements/R-<comp>-NNN.md`** — one normative requirement per file,
using RFC 2119 keywords. The filename *is* the requirement's id — no
frontmatter, no separate id field to keep in sync with it.

- Every `R-id` **MUST** be traceable forward to ≥1 acceptance criterion and
  backward to a rationale or decision record.
- An agent that must ask a clarifying question to execute a spec **MUST**
  surface it as a tracked assumption or an open question, never silently
  guess.

**`interface/`** — the public contract (types, endpoints, events, CLI,
and behavioral guarantees), split by kind:
- `interface/cli.md` — the CLI contract, if any.
- `interface/library.md` — the library/function contract, if any.
- `interface/data/<TypeName>.md` — one schema/type per file.
- `interface/guarantees/G-<comp>-NNN.md` — one behavioral/non-functional
  guarantee per file, that a *dependent* is entitled to rely on
  (consistency, ordering, idempotency, error-handling semantics, latency
  bounds). Like a requirement, each uses RFC 2119 keywords and its
  filename is its id. **Not** a place for internal implementation
  rationale — that stays in `requirements/`/`constraints.md`. (D2)

A component need not have all four. The generated interface **MUST**
match this content exactly; any divergence is a hard drift-check
failure.

**`acceptance/AC-<comp>-NNN.md`** — one acceptance criterion per file, in
the format of `specs/architecture/acceptance-criteria.md`. The filename
is the criterion's id.

**`constraints.md`** — one flat file of non-functional requirements
(perf, security, compatibility), each with a measurable target and a
measurement method.
