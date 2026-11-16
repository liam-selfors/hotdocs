# AC-UI-007

Covers: R-UI-007
Kind: generated-test

```gherkin
Given a faked check_readiness that appends every call's changed_ids to
  a log file the test controls, and returns scope "blast-radius" when
  changed_ids is given and "whole-corpus" otherwise
When render_tracker_ui runs first with changed_ids ["comp-foo"] and
  then again with no changed_ids
Then the log shows exactly two calls, ["comp-foo"] then null, and the
  second page shows "whole-corpus" while the first shows
  "blast-radius" together with "comp-foo"
```
