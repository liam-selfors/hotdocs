# R-AUTHOR-026

**R-AUTHOR-026** — A bundle MAY carry `module_names`, a list of module
  names. When it is non-empty, the prompt MUST name each of them, in
  order, as a module under test, written as the exact statement
  `import <name>`, in place of `R-AUTHOR-025`'s derived name, which the
  prompt then never offers as an import. A capability scenario's
  `component_id` (`capabilities/<P-id>`) names no module, so its caller
  passes the realizing components' modules here (`D198`). When it is
  absent or empty, `R-AUTHOR-025` applies.
