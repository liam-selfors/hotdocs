# AC-GEN-001

Covers: R-GEN-001
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle for comp-foo whose spec, interface,
  constraints and glossary are "SPEC-MARK", "IFACE-MARK", "CONS-MARK"
  and "GLOSS-MARK", whose dependency_interfaces, dependency_context and
  vars are {"comp-bar": "DI-MARK"}, {"comp-bar": "DC-MARK"} and
  {"VAR-X": "VAR-MARK"}, whose dependency_usage is {"comp-bar": ""},
  and a mock model that records what it was sent
When generate is called with that bundle and no retry_feedback
Then the recorded prompt's "## SPEC" section is "SPEC-MARK", its
  "## DEPENDENCY CONTEXT" section is "### comp-bar\nDC-MARK", each other
  marker is in its own section, and the prompt has no line
  "## DEPENDENCY USAGE", "## HINT_CODE" or "## RETRY_FEEDBACK"
```
