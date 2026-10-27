# AC-AUTHOR-010

Covers: R-AUTHOR-010
Kind: generated-test

```gherkin
Given any bundle
When author_test builds its prompt
Then the prompt sent to the model states that no DEPENDENCY is
  statically importable (never claiming this about the component under
  test itself), explicitly says the component under test is imported
  normally via a plain import/from-import with no custom loader needed,
  names the real <repo_root>/gen/<dependency-slug>/<module_name>.py
  (or <dependency-slug>/__init__.py) resolution path for a dependency,
  instructs writing a fake dependency module file always in the flat-
  module shape under a temporary repo_root rather than sys.modules
  injection or unittest.mock.patch by name, states module_name as the
  dependency's own slug with hyphens replaced by underscores (never a
  literal "__init__"), and includes a literal worked snippet showing
  sys.modules[module_name] = module assigned before
  spec.loader.exec_module(module) is called
```
