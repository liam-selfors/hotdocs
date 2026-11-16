# R-SURF-002

**R-SURF-002** — For each direct dependency in `depends_on`,
  `check_surface` MUST collect the names the candidate's `.py` files
  (outside `__pycache__`) use on it: every `<alias>.<name>`, not preceded
  by a word character or `.`, where `<alias>` is the dependency's module
  name or a name assigned on a line whose right side both calls one of
  `importlib.import_module(`, `module_from_spec(`, `exec_module(` or a
  function whose name starts `_load`, and contains the dependency's slug
  or module name as a quoted string; names starting `__` are ignored.
  It MUST then check, in one subprocess importing the dependency's
  module, each name with `hasattr`, or as an importable submodule
  `<module>.<name>`. Each missing name gives one `dependency_name`
  finding, `<dep-slug> has no <name>, which the candidate uses`. A
  dependency whose module does not import is skipped.
