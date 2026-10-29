# R-AUTHOR-012

**R-AUTHOR-012** — The prompt MUST always include the frontmatter
  fields `SPEC_GUIDELINES.md` requires on every frontmatter-bearing
  document: `id`, `title`, `status`, `owners` always required,
  `status` MUST be exactly one of `draft`/`ratified`/`deprecated`
  (`D105`). Applies to **every** such document a fixture constructs —
  `component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`
  (`D105`) — not a copy of the real corpus, since a
  precondition-checking component needs a genuinely lint-clean
  fixture to exercise anything past that check.

  Also MUST state every `requirements/` file needs a matching
  `acceptance/` file with a `Covers:` tag (`D105`, `R-LINT-008`), for
  every component the fixture constructs, not just the target; and
  `status: ratified` MUST also set a placeholder `last_ratified_commit`
  (`D107`, `R-LINT-002`).

  **MUST also state the opposite**: a unit file (`constraints.md`,
  or anything under `requirements/`, `interface/`, `acceptance/`)
  carries no frontmatter at all (`R-LINT-016`, `D115`) — the rule
  above over-applied to these.

  **MUST also state a test MUST NEVER `import yaml` or any other
  not-already-installed third-party package** (`D125` — the
  identical lesson `R-ASSEMBLE-012`/`D101` closed for a candidate's
  own code, not yet stated for test-authoring): write/parse
  frontmatter as plain text instead.

  Found only once a component depending on corpus-wide
  lint-cleanliness had `generated-test` criteria authored against it
  for the first time (`D102`): 6 of 13 authorings missed
  `title`/`owners`. See `R-AUTHOR-013`–`015` for further rounds.
