# R-AUTHOR-012

**R-AUTHOR-012** — The prompt MUST always include the frontmatter
  `SPEC_GUIDELINES.md` requires on every such document: `id`, `title`,
  `status`, `owners` always, `status` exactly one of
  `draft`/`ratified`/`deprecated` (`D105`). This applies to every
  frontmatter-bearing document a fixture constructs (`component.md`,
  `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`).

  It MUST also state: every `requirements/` file needs a matching
  `acceptance/` file with a `Covers:` tag, for every fixture component
  (`D105`, `R-LINT-008`); `status: ratified` also sets a placeholder
  `last_ratified_commit` (`D107`, `R-LINT-002`); a unit file
  (`constraints.md`, or anything under `requirements/`, `interface/`,
  `acceptance/`) carries no frontmatter at all (`R-LINT-016`, `D115`);
  and a test MUST NEVER `import yaml` or any other not-already-installed
  third-party package — write and parse frontmatter as plain text
  (`D125`).
