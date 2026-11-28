# R-LINT-036

**R-LINT-036** — For each component `component.md` or capability file
  whose frontmatter has a `drivers` line (`D373`), the linter MUST
  report one `fail` finding, `file` that file and `line` the line of
  its `drivers:` key, with exactly the message shown, for each item
  (read as `R-LINT-034` reads `assets`) that:

  - does not match `[a-z][a-z0-9-]*` in full:
    `driver '<item>' is not a driver name`;
  - has neither `<repo_root>/specs/architecture/test-driver-<item>.md`
    nor an adapter `gen/driver-<item>/driver_<module>.py` under
    `repo_root` or the tool root (`<module>` the name with `-` as `_`):
    `test driver '<item>' has no definition or adapter`;
  - for a component file only: is defined in the repository while
    that component's `depends_on` lacks `comp-driver-<item>`:
    `test driver '<item>' is defined in this repository; depends_on must list comp-driver-<item>`.

  An item failing the first check gets no further check. A block-style
  `drivers` list is `drivers must be one line: [a, b]`.
