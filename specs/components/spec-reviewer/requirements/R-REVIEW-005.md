# R-REVIEW-005

**R-REVIEW-005** — With `write_proposals=True` and at least one gap,
  `check` MUST write one file per criterion with gaps,
  `<repo_root>/.hotdocs/proposals/<criterion_id>.md`, replacing any
  earlier one, holding the line `# Proposals for <criterion_id>`, then
  for each gap a blank line and the lines `- kind: <kind>`,
  `  missing: <missing>`, `  target_file: <target_file>` and
  `  proposed_text: <proposed_text>`. It lists each path, relative to
  `repo_root`, in `proposals`. It MUST NOT write any other file, and
  without `write_proposals` it writes nothing.
