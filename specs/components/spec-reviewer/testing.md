# Testing spec-reviewer

**The synthetic corpus.** Every criterion's corpus lives under a fresh
temporary `repo_root` and MUST lint clean (`check` lints it first). A
component with a second requirement adds `requirements/R-FOO-002.md`
the same way: `# R-FOO-002`, a blank line, then its bold line; every
requirement file's first line is `# <its id>`, and every requirement
has a covering criterion.

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
