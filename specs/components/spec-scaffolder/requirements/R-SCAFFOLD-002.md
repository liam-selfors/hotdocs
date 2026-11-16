# R-SCAFFOLD-002

**R-SCAFFOLD-002** — `new_decision` MUST write
  `<repo_root>/specs/decisions/<id>.md`, `<id>` being
  `next_decision_id(repo_root)`, creating `specs/decisions/` if absent,
  and return that path. The file MUST be exactly these lines, each ending
  in a newline, the `builds_on` line present only when `builds_on` is
  non-empty and the `supersedes` line only when `supersedes` is given:

  ```
  ---
  id: <id>
  title: <title>
  status: draft
  owners: [<owners>]
  builds_on: [<builds_on>]
  supersedes: <supersedes>
  ---

  # <id> — <title>

  ## Context

  TODO.

  ## Decision

  TODO.

  ## Consequences

  TODO.
  ```

  It MUST raise `ValueError`, writing nothing, for an empty `title` or a
  `builds_on`/`supersedes` id with no file under `specs/decisions/`.
