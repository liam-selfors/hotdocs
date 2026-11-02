# R-AUTHOR-014

**R-AUTHOR-014** — The prompt MUST state that any list-valued
  frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) in
  a synthetic fixture (`R-AUTHOR-012`) MUST use YAML flow style
  (`[a, b]`), never block style. This corpus's frontmatter reader does
  not recognize block style as a list, and every real spec file already
  uses flow style (`D104`).
