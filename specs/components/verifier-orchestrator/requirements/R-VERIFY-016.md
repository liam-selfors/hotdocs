# R-VERIFY-016

**R-VERIFY-016** — A criterion's id MUST be taken exactly from its
  file's `# AC-...` heading — including an optional lowercase letter
  suffix such as `AC-FOO-003b` — and passed unchanged everywhere,
  including to `assemble_criterion`. Never case-transformed or
  re-derived from the file name (`D163`).
