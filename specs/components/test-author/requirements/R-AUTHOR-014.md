# R-AUTHOR-014

**R-AUTHOR-014** — The prompt MUST state that any list-valued
  frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`)
  in a synthetic fixture (`R-AUTHOR-012`) MUST use YAML flow style
  (`[a, b]`), never block style. This corpus's frontmatter reader does
  not recognize block style as a list at all, and every real spec
  file already uses flow style exclusively — not a new rule, only a
  statement of what's already true.

  Found by diagnosing: after `R-AUTHOR-013`'s fix, five of seven
  failures shared this one cause, confirmed by hand-patching one
  line per fixture (sandbox only), candidate passed cleanly (`D104`).
