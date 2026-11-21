# Testing spec-linter

**A clean corpus.** A test that needs a corpus with no findings at all
writes exactly these files under its temporary `repo_root`; `lint(None,
repo_root)` then reports no findings. A test needing particular findings
starts from it and changes only what its criterion names, so nothing else
is reported.

`specs/product/foo.md`:

````
---
id: P-FOO
title: Foo works
status: draft
owners: [team-a]
---

# Foo works

## Purpose

A foo can be made.

### CS-FOO-001
Covers: P-FOO
Kind: generated-test

```gherkin
Given nothing
When a foo is made
Then it exists
```
````

`specs/components/foo/component.md`:

```
---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
depends_on: []
realizes: [P-FOO]
sealed: false
---

# Foo

## Purpose

Makes a foo.

## Scope

**In scope:** making a foo. **Out of scope:** everything else.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
```

`specs/components/foo/requirements/R-FOO-001.md`:

```
# R-FOO-001

**R-FOO-001** — `make_foo()` MUST return the string `"foo"`.
```

`specs/components/foo/interface/library.md`:

````
# Library

One module file, `foo.py`.

```
make_foo() -> str
```
````

`specs/components/foo/acceptance/AC-FOO-001.md`:

````
# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given nothing
When make_foo() is called
Then the result is "foo"
```
````

`specs/components/foo/constraints.md`:

```
# Foo — Non-Functional Constraints

- **Pure.** No I/O.
```

**One finding of a given severity.** From the clean corpus, adding
`specs/components/foo/interface/cli.md` (any fenced block, cited by no
requirement) gives exactly one `warn`, `R-LINT-031`; deleting the
`Kind: generated-test` line of `AC-FOO-001.md` gives exactly one `fail`,
`R-LINT-010`. Every acceptance file needs both its `Covers:` and `Kind:`
lines, and every requirement an RFC 2119 keyword, or the corpus has
fail findings a criterion did not ask for.
