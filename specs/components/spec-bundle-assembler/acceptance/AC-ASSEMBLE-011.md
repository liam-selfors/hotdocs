# AC-ASSEMBLE-011

Covers: R-ASSEMBLE-011
Kind: compiled

```gherkin
Given a component that depends_on comp-bar, and comp-bar has real code
  under gen/bar/ defining a public function bar_get(key: str) -> str
When assemble runs for the dependent component
Then dependency_usage["comp-bar"] names bar_get's real, currently-
  importable module path and includes its signature and docstring —
  and, given a second dependency comp-baz with no real gen/ code at all,
  dependency_usage["comp-baz"] is an empty string, not an error
```
