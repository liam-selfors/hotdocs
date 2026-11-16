# AC-SCENARIO-010

Covers: R-SCENARIO-007
Kind: generated-test

```gherkin
Given a capability P-X realized by comp-foo and comp-bar, with
  specs/components/foo/interface/library.md holding "FOO_IFACE", bar's
  holding "BAR_IFACE", specs/glossary.md holding "GLOSS", and a
  generated-test scenario CS-X-001 whose fake author_test records its
  arguments and returns a passing test
When run_capability_gates("P-X", repo_root, "m", seed=3,
  llm_backend=<sentinel>) is called
Then author_test was called once with model "m", seed 3, repo_root, and
  the sentinel backend, and its bundle has component_id
  "capabilities/P-X", criterion_id "CS-X-001", covers P-X,
  criterion_text the scenario's gherkin, requirement_text containing the
  capability file's text, glossary "GLOSS", dependency_interfaces {},
  module_names ["bar", "foo"], and interface containing "## comp-bar", "BAR_IFACE", "## comp-foo",
  and "FOO_IFACE" in that order
```
