# R-LINT-019

**R-LINT-019** — No line in any spec file (including its frontmatter block)
  MUST end in trailing whitespace. A fail-severity finding, not a warning.
  `spec_bundle_hash` is a function of the bundle's raw bytes — Markdown
  is not whitespace-insensitive (trailing spaces are CommonMark's
  hard-line-break syntax), so this rule keeps that byte difference from
  ever reaching a committed file, keeping the hash simple and trustworthy.
