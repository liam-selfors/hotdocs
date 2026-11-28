---
id: arch-glossary-and-citations
title: Glossary and Citations
status: draft
owners: [pipeline-team]
depends_on: []
---

# Glossary and Citations

The rules for the glossary, for decision records, and for citing a
decision or a glossary entry, moved here from `SPEC_GUIDELINES.md` so a
component that checks them reads only these (`D381`).

## Decision citations

A bare `D<N>` citation refers to `specs/decisions/D<N>.md`, unless the
surrounding text names `notes/initial-ideas.md` explicitly (whose own
informal `D1`–`D14` numbering is separate).

## Decision records

A decision record (`specs/decisions/<id>.md`) is ADR-style and
append-only. Once a decision record is ratified it is immutable — a
change in direction is a new, superseding record (`supersedes` field),
never an edit to the old one, with one narrow, sanctioned exception: the
superseded record's own `status` field flips to `deprecated` as part of
that same change. `builds_on` lists the prior decisions a record's
reasoning depends on, without replacing any of them.

- A decision record **MUST** cover exactly one topic.
- Every `D<N>` citation **MUST** point to the specific decision
  responsible for the specific fact stated, never assumed correct because
  it merely resolves.

## Glossary

`specs/glossary.md` is a single file, no frontmatter, no per-spec entry
limit. (D14)

- Specs **MUST** use glossary terms as defined; a component's `Definitions`
  section may only add deltas, never silently redefine a glossary term.
- The glossary **MUST NOT** be sharded by a size rule. The only legitimate
  split is a deliberate `architecture/`-level bounded-context decision (two
  subsystems that genuinely don't share vocabulary) — never a routine
  response to word count.

## Glossary entries and their citation

A glossary entry is a line starting `- **<Term>**` (a list item whose
bolded text is the entry's header), its definition following on that
line and any continuation lines until the next such item (`D241`).
A citation of an existing glossary entry **MUST** quote its bolded
header exactly (e.g. `` the glossary's "Criterion test filename" ``)
— `R-CITE-003` checks this resolves to a real entry, as `R-CITE-001`
does for `D<N>` citations and `R-CITE-002` does for section-heading
pointers.
