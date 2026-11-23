# R-SURF-002

**R-SURF-002** — For each direct dependency in `depends_on`,
  `check_surface` MUST collect the names the candidate's `.py` files
  (outside `__pycache__`) use on it, from each file's syntax tree
  (`ast.parse`) and never from its text (`D362`): the `attr` of every
  `ast.Attribute` node whose `value` is an `ast.Name` with id `<alias>`.
  `bar.py` inside a string literal, or `bar.x` in a comment or a
  docstring, is no use; a file that does not parse gives no names.
  `<alias>` is the dependency's module
  name or a name assigned on a line whose right side both calls one of
  `importlib.import_module(`, `module_from_spec(`, `exec_module(` or a
  function whose name starts `_load`, and contains the dependency's slug
  or module name as a quoted string; names starting `__` are ignored.
  It MUST then check, in one subprocess of `R-SURF-006`'s interpreter
  importing the dependency's module, each name with `hasattr`, or as an importable submodule
  `<module>.<name>`. Each missing name gives one `dependency_name`
  finding, `<dep-slug> has no <name>, which the candidate uses`. A
  dependency whose module does not import is skipped.
