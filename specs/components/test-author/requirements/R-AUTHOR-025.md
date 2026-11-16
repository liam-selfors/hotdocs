# R-AUTHOR-025

**R-AUTHOR-025** — The prompt MUST name the component under test's own
  module concretely: its slug (`component_id` without `comp-`) with
  every hyphen replaced by an underscore, so `comp-foo-bar` is
  `foo_bar`, written as the exact statement `import foo_bar` — never
  left for the test author to infer from a function name or from the
  `component_id` itself (`comp_foo_bar` is wrong). The generator may
  lay the module out as `<module>.py` or a `<module>/` package; the
  import is the same either way (`D189`).
