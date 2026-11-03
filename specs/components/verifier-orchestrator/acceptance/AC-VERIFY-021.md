# AC-VERIFY-021

Covers: R-VERIFY-018
Kind: generated-test

```gherkin
Given a component with one passing compiled criterion
When main(["comp-foo", "--repo-root=<root>", "--format=json"]) runs,
  and main(["comp-foo", "--repo-root", "<root>", "--format", "text"])
Then both return 0, the first prints JSON whose overall is "pass", and
  the second prints "comp-foo: pass" then indented criterion lines

Given the same component with a failing criterion
When main(["comp-foo", "--repo-root=<root>"]) runs
Then it returns 1

Given no arguments, --format=bogus, an unknown argument, "--repo-root"
  last with no value, or "comp-nope" with no component.md
When main runs
Then it returns 2, and stderr names "hotdocs verify-component"
```
