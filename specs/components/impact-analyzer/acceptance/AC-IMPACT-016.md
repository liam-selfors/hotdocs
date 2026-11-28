# AC-IMPACT-016

Covers: R-IMPACT-012
Kind: generated-test

```gherkin
Given testing.md's git fixture with components comp-foo and comp-bar,
  comp-bar depending on comp-foo, comp-foo holding
  requirements/R-FOO-001.md and acceptance/AC-FOO-001.md, and, in the
  changed state, only R-FOO-001.md's text edited
When compute_blast_radius(["R-FOO-001"], repo) runs, and again with
  ["AC-FOO-001", "R-FOO-001"], and again with ["R-NOPE-001"]
Then the first gives impacted exactly [{"component_id": "comp-foo",
  "reason": "direct", "via": None, "guarantee_ids": None}]
  (comp-bar is not impacted, since no interface file changed), the
  second gives that same single entry, and
  the third gives an empty impacted list and precondition_error None
```
