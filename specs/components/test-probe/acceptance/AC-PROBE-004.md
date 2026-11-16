# AC-PROBE-004

Covers: R-PROBE-004
Kind: generated-test

```gherkin
Given a criterion bundle whose dependency_interfaces is
  {"comp-bar": "bar_get(key: str, default: dict[str, str]) -> str\nbar_put(*, key: str) -> None"}
  and a test source defining, at top level, "def bar_get(key):",
  "def bar_put(key):", "def other(a, b, c):" and "alias = bar_get", plus a
  test function calling none of them
When probe(source, bundle, "slugify") is called
Then the findings hold exactly one fake_signature_mismatch finding, on
  bar_get's def line, with message
  "bar_get takes 1 parameters; the interface of comp-bar gives 2"

Given the same bundle and a source whose fake is "def bar_get(*args):"
When probe(source, bundle, "slugify") is called
Then no finding has kind "fake_signature_mismatch"
```
