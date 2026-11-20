# Testing impact-analyzer

## The git fixture

Every criterion builds its corpus in a fresh directory `<repo>`
(pytest's `tmp_path`) and makes it a git repository this way, even when
nothing in it changes:

1. Write the "before" corpus.
2. Run `git init -q -b main`, `git add -A`, `git commit -q -m A`. Run
   every git command with `cwd=<repo>` as
   `git -c user.name=hotdocs-test -c user.email=test@example.com -c commit.gpgsign=false ...`.
   Add no remote.
3. Run `git switch -q -c feature`.
4. Write the "changed" state into the working tree. Leave it
   uncommitted or commit it on `feature`; both give the same result,
   because the analyzer compares each file at the merge-base of `HEAD`
   and `main` (commit A) with the working tree. Never commit the changed
   state on `main`: it then belongs to commit A and is no change at all.

"Changed" in a criterion means the file in the working tree differs
from commit A: edited, added or deleted. "Unchanged" or "byte-identical"
means equal to commit A. A criterion that names its own commits builds
them as it says, still forking `feature` from A on `main`. Never skip
the repository: with no git history every interface file present
counts as changed.

## A lint-clean fixture component

The analyzer refuses a corpus that does not lint clean, so build each
component `comp-<slug>` exactly so (`<SLUG>` is the slug upper-cased,
`<Slug>` title-cased; use one-word slugs), plus `specs/glossary.md`
holding `# Glossary\n\n- **Fixture** — a test component.\n`:

- `specs/components/<slug>/component.md`: the lines `---`,
  `id: comp-<slug>`, `title: <Slug>`, `status: draft`,
  `owners: [test-team]`, `sealed: true`, `source_path: legacy/<slug>/`,
  then any `depends_on: [...]` and `depends_on_guarantees: [...]` lines
  (flow lists), then `---`; a blank line, `# <Slug>`, and the sections
  `## Purpose`, `## Scope`, `## Definitions`, `## Behavior`,
  `## Interfaces`, `## Acceptance criteria`, `## Open questions`,
  `## Change log`, each followed by a blank line and one line of text.
- `requirements/R-<SLUG>-001.md`:
  `# R-<SLUG>-001\n\nThe component MUST return its input unchanged.\n`
- `acceptance/AC-<SLUG>-001.md`: `# AC-<SLUG>-001`, a blank line,
  `Covers: R-<SLUG>-001`, `Kind: generated-test`, a blank line, and a
  fenced `gherkin` block of `Given 1`, `When it runs`, `Then it returns 1`.
- `constraints.md`:
  `# Constraints\n\n- The component MUST finish within 1 second.\n`
- `interface/library.md`:
  `# Library\n\n` then a fenced block holding `run(x: int) -> int`.
  Change it by changing that signature.
- each guarantee `interface/guarantees/G-<SLUG>-NNN.md`:
  `# G-<SLUG>-NNN\n\nThe component MUST <one sentence>.\n`. Change it
  by changing the sentence.

`sealed: true` with a `source_path` lets a fixture component omit
`realizes`. A `depends_on` naming a component that does not exist is
the simplest lint failure for a precondition-error case.

## The CLI

Call `impact_analyzer.main(argv)` in-process and read stdout and stderr
with pytest's `capsys`; `<repo>` in an argument list is `str(<repo>)`.
