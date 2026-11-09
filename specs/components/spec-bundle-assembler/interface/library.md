# Library

```
assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle
assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle
```

Both are pure functions over the filesystem state at `repo_root` — no
network access, no model calls, no side effects.

## Test fixtures

Every criterion's synthetic corpus lives under a fresh temporary
`repo_root`, and `assemble`/`assemble_criterion` lint it first
(`R-ASSEMBLE-005`), so it MUST pass `spec-linter`. A test never imports
`spec_linter` (it is not importable by name); it builds files that pass.
Each file is written exactly as shown, `---` in column 0 of line 1,
never through `textwrap.dedent` over interpolated text.

`specs/glossary.md`:

```
# Glossary

- **Foo** — a test term.
```

`specs/components/foo/component.md` (a dependent adds
`depends_on: [comp-foo]` in place of `[]`, with its own id and
`source_path`):

```
---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
```

`requirements/R-FOO-001.md`: `# R-FOO-001`, a blank line, then
`**R-FOO-001** — \`foo(x)\` MUST return \`2 * x\`.`

`acceptance/AC-FOO-001.md`:

````
# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
````

`interface/library.md`: `# Library` and a fenced `foo(x: int) -> int`.
`constraints.md`: `# Constraints` and `None.`

Deleting the `Kind:` line from an acceptance file is a hard lint
failure, the way to build a corpus `assemble` refuses. A sealed
component's real code goes under its `source_path`
(`legacy/foo/foo.py`), never `gen/`.
