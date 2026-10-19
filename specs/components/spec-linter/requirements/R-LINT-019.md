# R-LINT-019

**R-LINT-019** — No line in any spec file (including its frontmatter block)
  MUST end in trailing whitespace. A fail-severity finding, not a warning.

  This resolves item 9's cache-hit-rate concern (`spec-bundle-assembler`'s
  Open Questions) without weakening `spec_bundle_hash`: that hash is
  confirmed to be, and stay, a function of the bundle's **raw bytes** —
  Markdown is not whitespace-insensitive (two-or-more trailing spaces are
  CommonMark's hard-line-break syntax; indentation is load-bearing inside
  nested lists and code fences), so there is no universally-safe
  normalization rule to hash against instead. Rather than teach the hash
  function to ignore a class of byte differences it cannot always safely
  ignore, this rule keeps the difference from ever reaching a committed
  file in the first place, so the cache-hit benefit is real and the hash
  function stays simple and trustworthy.
