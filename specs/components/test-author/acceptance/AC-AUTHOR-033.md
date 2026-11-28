# AC-AUTHOR-033

Covers: R-AUTHOR-027
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is {},
  a test-probe stand-in returning ok true, and a mock model that records
  each prompt, reads the nonce n from the last line of the prompt
  that starts "-----BEGIN FILE " (a repair prompt repeats the first
  prompt, then asks for a fresh nonce), and replies "no markers here" to its
  first call and "-----BEGIN FILE " + n + "-----\nimport x\n-----END FILE " + n + "-----"
  to its second
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the result's model_call_error is None, its repair_attempts is 1,
  and the second recorded prompt contains the line
  "Your reply held no BEGIN FILE / END FILE marker pair with the nonce <n1>.",
  <n1> being the nonce of the first prompt

Given the same, except the mock replies "no markers here" to every call
When author_test is called
Then model_call_error's category is "missing_file_markers", its message
  is exactly "model reply held no matching BEGIN/END FILE markers; reply
  began: 'no markers here'", repair_attempts is 2, file is None, and
  nothing is written under repo_root
```
