# R-IMPACT-004

**R-IMPACT-004** — For a changed `specs/vars/` declaration, the analyzer
  MUST treat it the same way as a changed `interface/` file: every
  component with a `uses_var` reference to that declaration is included,
  tagged `transitive-var`, naming the changed variable.
