# AC-ASSEMBLE-011

Covers: R-ASSEMBLE-011
Kind: generated-test

```gherkin
Given a component that depends_on comp-bar, and comp-bar has real code
  under its source_path defining a public function bar_get(key: str) -> str
When assemble runs for the dependent component
Then dependency_usage["comp-bar"] contains the module name "bar", the
  directory "legacy/bar/", "bar_get", the text of
  str(inspect.signature(bar_get)), and its docstring's first line —
  and, given a second dependency comp-baz with no real code at all,
  dependency_usage["comp-baz"] is an empty string, not an error
```

The corpus is `interface/library.md`'s test fixture: comp-foo depends
on comp-bar and comp-baz, all three sealed as the fixture shows. comp-bar's real
code is `legacy/bar/bar.py`, under its `source_path: legacy/bar/`;
comp-baz has no file under `legacy/baz/`. No component is unsealed and
none drops its `source_path`, which lint rejects.
