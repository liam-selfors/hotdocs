# R-SCAFFOLD-005

**R-SCAFFOLD-005** — `new_component` MUST create
  `<repo_root>/specs/components/<slug>/` holding `component.md`,
  `constraints.md`, and the directories `requirements/`, `acceptance/`,
  `interface/` and `interface/data/`, each holding one empty `.gitkeep`
  file, and return the directory's path. `title` defaults to the slug's
  words, each capitalized, joined by spaces (`my-thing` gives
  `My Thing`). `component.md` MUST be exactly:

  ```
  ---
  id: comp-<slug>
  title: <title>
  status: draft
  owners: [<owners>]
  depends_on: [<depends_on>]
  realizes: [<realizes>]
  sealed: <true or false>
  ---

  # <title>

  ## Purpose

  TODO.

  ## Scope

  TODO.

  ## Definitions

  No deltas from `specs/glossary.md`.

  ## Behavior

  See `requirements/`.

  ## Interfaces

  See `interface/`.

  ## Data

  See `interface/data/`.

  ## Acceptance criteria

  See `acceptance/`.

  ## Non-functional constraints

  See `constraints.md`.

  ## Open questions

  None.

  ## Change log

  - Initial draft.
  ```

  and `constraints.md` exactly `# <title> — Non-Functional Constraints`,
  a blank line, then `- TODO.`, each line ending in a newline. Empty
  lists are written `[]`. It MUST raise `ValueError` for a slug that is
  not kebab-case and `FileExistsError` when the directory exists, writing
  nothing in either case.
