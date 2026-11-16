# AC-IMPACT-010

Covers: R-IMPACT-010
Kind: generated-test

```gherkin
Given a real git repo with a default branch at commit A, a feature
  branch forked from A with two further commits (B then C), and
  comp-foo's interface/library.md changed between A and C (not between
  B and C) — and comp-bar depends_on comp-foo
When hotdocs impact --changed comp-foo runs with HEAD at C
Then the report's impacted list contains comp-bar with reason
  "transitive-interface" — detected by comparing library.md's content
  at the merge-base (commit A) against its current working-tree
  content, not against HEAD~1 (which would compare against C's parent,
  commit B, and could miss or misattribute the actual change)
```
