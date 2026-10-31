# AC-UI-005

Covers: R-UI-005
Kind: generated-test

```gherkin
Given a faked provenance-tracker whose check_readiness reports comp-new
  and comp-old both as misses (hit false) and whose
  last_requirement_failures returns [], a .hotdocs/attempts/comp-old/
  directory holding one AttemptRecord, and no
  .hotdocs/attempts/comp-new/ directory
When render_tracker_ui runs
Then comp-new's status is "not-attempted" and its node element's text
  contains "not yet attempted", while comp-old's status is "missing"

Given the same repo_root with no .hotdocs/ directory at all
When render_tracker_ui runs
Then it writes index.html without raising, and both nodes are
  "not-attempted"
```
