# AC-AUTHOR-010

Covers: R-AUTHOR-010
Kind: generated-test

```gherkin
Given any bundle
When author_test builds its prompt
Then the prompt sent to the model states that no component in this
  corpus is statically importable, names the real
  <repo_root>/gen/<dependency-slug>/<module_name>.py (or
  <dependency-slug>/__init__.py) resolution path, instructs writing a
  fake module file at that path under a temporary repo_root rather than
  sys.modules injection or unittest.mock.patch by name, and includes a
  literal worked snippet showing sys.modules[module_name] = module
  assigned before spec.loader.exec_module(module) is called
```
