---
id: arch-graph-query-engine-fixture
title: Graph Query Engine Test Fixture
status: draft
owners: [pipeline-team]
depends_on: []
---

# Graph Query Engine Test Fixture

## Purpose

The one synthetic corpus a test of `graph-query-engine` writes under a
temporary `repo_root`, and what each view returns for it, so that no
test reads the repository's own specs (`D333`): a mutation run copies
only `gen/`, where those specs do not exist (`D324`).

## Rules

A test writes these files under `repo_root`, each exactly as shown
(`\n` line endings, one trailing newline), opens a DuckDB connection,
runs `INSTALL yaml FROM community` and `LOAD yaml`, then calls
`load_views(con, repo_root)`.

- `specs/components/foo/component.md`: the frontmatter lines `id:
  comp-foo`, `title: Foo`, `status: draft`, `owners: [team]`,
  `depends_on: [comp-bar]`, `realizes: [P-X]`, `uses_var: [VAR-X]`,
  `depends_on_guarantees: [G-BAR-001]` between `---` lines, a blank
  line, `# Foo`, a blank line, `one two three`.
- `specs/components/bar/component.md`: frontmatter `id: comp-bar`,
  `title: Bar`, `status: draft`, `owners: [team]`, `realizes: [P-X]`,
  then a blank line and `# Bar`.
- `specs/components/foo/requirements/R-FOO-001.md`: `# R-FOO-001`, a
  blank line, `foo MUST work.`; `R-FOO-002.md`: `# R-FOO-002`, a blank
  line, `foo MUST stop.`
- `specs/components/foo/acceptance/AC-FOO-001.md`: `# AC-FOO-001`, a
  blank line, `Covers: R-FOO-001`, `Kind: generated-test`.
- `specs/components/foo/interface/guarantees/G-FOO-001.md`:
  `# G-FOO-001`, a blank line, `foo never fails.`
- `specs/product/x.md`: frontmatter `id: P-X`, `title: X`,
  `status: draft`, `owners: [team]`, then `# X`, and two scenarios,
  each `### CS-X-001` (then `CS-X-002`) followed directly by the line
  `Covers: P-X`.
- `specs/vars/x.md`: frontmatter `id: VAR-X`, `title: V`,
  `status: draft`, `owners: [team]`, then `# V`.
- `specs/decisions/D1.md`: frontmatter `id: D1`, `title: One`,
  `status: ratified`, `owners: [team]`; `D2.md`: `id: D2`,
  `title: Two`, `status: draft`, `owners: [team]`, `supersedes: D1`,
  `builds_on: [D1]`; each then `# D1` or `# D2`.
- `README.md` in each of `specs/product/`, `specs/vars/` and
  `specs/decisions/`: `# Readme`, a blank line, `Notes.`, and no
  frontmatter.

What the views return for it:

| View | Result |
| --- | --- |
| `nodes` rows per `kind` | `component` 2, `capability` 1, `var` 1, `decision` 2, `guarantee` 1, `requirement` 2, `acceptance` 1, `capability_scenario` 2; no `id` is null |
| `edges` rows per `edge_type` | `depends_on` 1, `realizes` 2, `uses_var` 1, `depends_on_guarantees` 1, `covers` 3, `supersedes` 1, `builds_on` 1 |
| `component_docs` | 2 rows; `comp-foo`'s `title` is `Foo`, `depends_on` is `["comp-bar"]` and `body` contains `one two three` |
| `component_size` | `foo` 26, `bar` 2 |
| `bundle_size` | `foo` `generator_words` 20, `criterion_words_max` 16; `bar` 2, 0 |
