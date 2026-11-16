# R-AUTHOR-014

**R-AUTHOR-014** — The prompt MUST state that any list-valued
  frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) in
  a synthetic fixture (`R-AUTHOR-012`) MUST use YAML flow style,
  showing the literal example `[a, b]`, never block style, which the
  frontmatter reader does not read as a list (`D104`).
