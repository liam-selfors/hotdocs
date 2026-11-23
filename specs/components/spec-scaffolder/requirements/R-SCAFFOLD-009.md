# R-SCAFFOLD-009

**R-SCAFFOLD-009** — `new_capability` MUST write
  `<repo_root>/specs/product/<name>.md`, creating `specs/product/` when
  absent, and return its path (`D364`). `<NAME>` is `<name>` uppercased
  (`order-book` gives `ORDER-BOOK`); `title` defaults to
  the name's words, each capitalized, joined by spaces (`Order Book`). The file MUST be exactly these lines, each
  ending in a newline:

  ```
  ---
  id: P-<NAME>
  title: <title>
  status: draft
  owners: [<owners>]
  ---

  # <title>

  ## Purpose

  TODO.
  ```

  It MUST raise `ValueError` for a name that is not kebab-case and
  `FileExistsError` when the file exists, writing nothing in either
  case.
