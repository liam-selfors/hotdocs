# AC-PROBE-004

Covers: R-PROBE-004
Kind: generated-test

```gherkin
Given a criterion bundle whose dependency_interfaces is
  {"comp-bar": "bar_get(key: str, default: dict[str, str]) -> str\nbar_put(*, key: str) -> None"}
  and a test source defining, at top level, "def bar_get(key):",
  "def bar_put(key):", "def other(a, b, c):" and "alias = bar_get", plus a
  test function whose body is
  'monkeypatch.setattr(target, "bar_get", alias)' and
  'monkeypatch.setattr(target, "bar_put", bar_put)'
When probe(source, bundle, "slugify") is called
Then the findings hold exactly one fake_signature_mismatch finding, on
  bar_get's def line, with message
  "bar_get takes 1 parameters; the interface of comp-bar gives 2"

Given the same bundle and a source whose fake, installed the same way,
  is "def bar_get(*args):"
When probe(source, bundle, "slugify") is called
Then no finding has kind "fake_signature_mismatch"

Given the same bundle and a source whose top-level "def bar_get():" is
  a helper its test function calls and installs nowhere
When probe(source, bundle, "slugify") is called
Then no finding has kind "fake_signature_mismatch"

Given dependency_interfaces {"comp-bar": "bar_get(a: int, /, b: dict[str, tuple[int, int]], *, c: str) -> str"}
  and a test source whose top-level "def bar_get(a, b, *, c):" matches
  and whose line 10 starts a triple-quoted string literal whose third
  line is "def bar_get(a, b):", plus "x = y = bar_get"
When probe(source, bundle, "slugify") is called
Then the findings hold exactly one fake_signature_mismatch finding, with
  line 12 and message
  "bar_get takes 2 parameters; the interface of comp-bar gives 3"
```
