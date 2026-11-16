# AC-AGENT-008

Covers: R-AGENT-008
Kind: generated-test

```gherkin
Given a repo_root whose specs/components/widget/acceptance/AC-W-1.md and
  verification/widget/test_w.py each contain "CANARY-7f3a", a generator
  stand-in, and a loop stand-in whose script calls list_files on
  "bundle", "work" and "scratch", read_file on every file listed, and
  read_file on "../specs/components/widget/acceptance/AC-W-1.md",
  "bundle/../../verification/widget/test_w.py",
  <repo_root>/specs/components/widget/acceptance/AC-W-1.md as an
  absolute path, then finish
When generate_agentic(bundle for comp-widget, "m", repo_root=<repo_root>)
  is called
Then "CANARY-7f3a" appears in no recorded tool result, nor in the system
  text or prompt the loop stand-in received
```
