# AC-IMPACT-014

Covers: R-IMPACT-011
Kind: generated-test

```gherkin
Given a lint-clean git fixture with comp-foo, comp-qux (guarantees
  G-QUX-001 and G-QUX-002), comp-bar with depends_on: [comp-foo, comp-qux]
  and comp-baz with depends_on: [comp-qux], where on the feature branch
  comp-foo's interface/library.md and both of comp-qux's guarantee files
  changed
When main(["--changed", "comp-foo", "comp-qux", "--repo-root", <repo>])
  runs
Then it returns 0, stderr is empty and stdout is exactly
  "comp-foo\tdirect\n"
  "comp-qux\tdirect\n"
  "comp-bar\ttransitive-interface\tvia comp-foo\n"
  "comp-baz\ttransitive-guarantee\tvia comp-qux\tG-QUX-001,G-QUX-002\n"
And main(["--changed=comp-qux", "--changed", "comp-foo",
  "--repo-root=" + <repo>, "--format", "text"]) prints the same and
  returns 0

Given the same fixture after comp-baz's depends_on also names
  comp-missing
When main(["--changed", "comp-foo", "--repo-root", <repo>]) runs
Then it returns 1 and stdout is one line starting "precondition error: "
And with "--format=json" added it returns 1 and stdout parses as JSON
  with impacted [] and a non-null string precondition_error
```
