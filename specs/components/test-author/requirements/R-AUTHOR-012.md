# R-AUTHOR-012

**R-AUTHOR-012** — The prompt MUST always include the frontmatter
  fields `SPEC_GUIDELINES.md` requires on every such document —
  `id`, `title`, `status`, `owners` always required, `status` exactly
  one of `draft`/`ratified`/`deprecated` (`D105`) — applying to
  **every** frontmatter-bearing document a fixture constructs
  (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`),
  not a copy of the real corpus: a precondition-checking component
  needs a genuinely lint-clean fixture to exercise anything past
  that check.

  Also MUST state: every `requirements/` file needs a matching
  `acceptance/` file with a `Covers:` tag, for every fixture
  component, not just the target (`D105`, `R-LINT-008`); and
  `status: ratified` also sets a placeholder `last_ratified_commit`
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

  Found at `D102` (6 of 13 authorings missed `title`/`owners`); see
  `R-AUTHOR-013`–`015` for further rounds.
