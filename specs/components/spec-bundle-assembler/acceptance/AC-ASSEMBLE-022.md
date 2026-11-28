# AC-ASSEMBLE-022

Covers: R-ASSEMBLE-007
Kind: generated-test

```gherkin
Given the library's test fixture with a dependent comp-baz, and
  legacy/foo/foo.py holding "def foo(x):\n    return 2 * x\n"
When assemble("comp-baz") runs, then again after foo.py's "2 * x"
  becomes "x + x"
Then the two spec_bundle_hash values differ, their spec_bundle_parts
  "spec" values are equal, and their "dependency_code" values differ

When assemble("comp-baz") runs, then again after comp-baz's
  requirement file gains a final line "Note."
Then the two "spec" values differ and the two "dependency_code" values
  are equal
```
