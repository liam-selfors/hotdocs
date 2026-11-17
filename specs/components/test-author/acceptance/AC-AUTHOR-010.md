# AC-AUTHOR-010

Covers: R-AUTHOR-010
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is {},
  and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains the line
  "The component under test itself needs no custom loader: a plain `import widget_maker`."
  and the line
  "A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`."
  and the line "        sys.modules[module_name] = module" occurs in it
  before the line "        spec.loader.exec_module(module)"
```
