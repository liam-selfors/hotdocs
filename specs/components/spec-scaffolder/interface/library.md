# Library

One module file, `spec_scaffolder.py`, never a package.

```
next_decision_id(repo_root: Path) -> str
new_decision(repo_root: Path, title: str, owners: list[str] | None = None,
             builds_on: list[str] | None = None, supersedes: str | None = None) -> Path
ratify(repo_root: Path, decision_id: str) -> list[Path]
record_commit(repo_root: Path, decision_id: str, commit: str | None = None) -> str
new_component(repo_root: Path, slug: str, title: str | None = None,
              owners: list[str] | None = None, depends_on: list[str] | None = None,
              realizes: list[str] | None = None, sealed: bool = False) -> Path
new_kind(repo_root: Path, kind: str, title: str | None = None,
         owners: list[str] | None = None, realizes: list[str] | None = None) -> list[Path]
new_capability(repo_root: Path, name: str, title: str | None = None,
               owners: list[str] | None = None) -> Path
main(argv: list[str] | None = None) -> int
```

Decision records live at `<repo_root>/specs/decisions/D<N>.md`; components
at `<repo_root>/specs/components/<slug>/`; capabilities at
`<repo_root>/specs/product/<name>.md`. `owners` defaults to
`["unassigned"]`.

**Errors.** Each function raises, never returns an error value:

- `ValueError` for an invalid argument: an empty `title`; a `slug` that is
  not kebab-case (`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`); a `decision_id` not of
  the form `D<N>`; a `kind` not kebab-case, or `python`; a capability `name` not kebab-case; a `builds_on` or `supersedes` id with no file under
  `specs/decisions/`.
- `FileExistsError` when `new_decision`'s, `new_component`'s or
  `new_capability`'s target already exists, or `new_kind`'s definition or component directory does.
- `LookupError` when `ratify` or `record_commit` names a decision with no
  file; when `ratify` finds it already ratified; when `record_commit`
  finds it not ratified, finds `last_ratified_commit` already holding a
  value other than `PENDING-COMMIT`, or, with no `commit` given, finds no
  commit that touched the file.

**Frontmatter format.** Lists are flow-style with `, ` between items
(`owners: [team-a, team-b]`); `builds_on` is written only when non-empty;
`supersedes` is a scalar line (`supersedes: D12`), written only when given.

Test fixtures: a `repo_root` needs only a `specs/decisions/` directory for
the decision functions, and only `specs/` for `new_component`,
`new_kind` and `new_capability`;
`record_commit` without `commit` needs `repo_root` to be a git repository
in which the record has been committed.

Implements: `specs/architecture/cli-conventions.md`
