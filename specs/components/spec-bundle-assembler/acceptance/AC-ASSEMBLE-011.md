# AC-ASSEMBLE-011

Covers: R-ASSEMBLE-011
Kind: generated-test

```gherkin
Given a component that depends_on comp-bar, and comp-bar has real code
  under gen/bar/ defining a public function bar_get(key: str) -> str
When assemble runs for the dependent component
Then dependency_usage["comp-bar"] names bar_get's real, currently-
  importable module path and includes its signature and docstring —
  and, given a second dependency comp-baz with no real gen/ code at all,
  dependency_usage["comp-baz"] is an empty string, not an error
```

The synthetic corpus must itself pass spec-linter, since `assemble`
refuses one that does not (`D177`). So every component is `sealed: true`
with a `source_path` (comp-bar's is `gen/bar`), `status: draft`, and an
`owners` list; every requirement's text uses the uppercase word MUST;
every acceptance file carries a `Covers:` line, a `Kind: generated-test`
line, and a Given/When/Then block; and every file with frontmatter begins,
on its very first line and in column 0, with `---` — so fixture text is
never built by `textwrap.dedent` over an interpolated multi-line value.
