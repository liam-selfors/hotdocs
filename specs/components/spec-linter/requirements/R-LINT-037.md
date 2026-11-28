# R-LINT-037

**R-LINT-037** — A directory directly under `specs/components/` that holds
  any file, at any depth, but no `component.md` MUST be one `fail`
  finding, `rule_id` `R-LINT-037`, `file` the directory's path relative
  to `repo_root` with a trailing `/`, `line` `1`, and `message`
  `specs/components/<name>/ has no component.md`. No other rule examines
  such a directory or raises on it; its other files are not checked.
