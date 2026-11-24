# AC-SCENARIO-014

Covers: R-SCENARIO-007
Kind: generated-test

```gherkin
Given a capability P-X realized by comp-foo, with
  specs/components/foo/interface/library.md holding "FOO_IFACE" and
  specs/glossary.md holding "GLOSS", one generated-test scenario
  CS-X-001, no file under verification/capabilities/P-X/, and
  gen/test-author/test_author.py a fake whose author_test appends each
  bundle it receives, as JSON, to <repo_root>/calls.jsonl and returns
  {"model_call_error": None, "file": {"path":
  "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
  "content": "def test_x():\n    assert True\n"}}
When run_capability_gates("P-X", repo_root, "m") is called; then the
  test writes verification/capabilities/P-X/generated-test/test_cs_x_001.py
  as the line "# hotdocs-criterion: sha256:<hex>", <hex> computed from
  the recorded bundle as R-SCENARIO-007 says, a newline and
  "def test_x():\n    assert True\n", deletes
  verification/capabilities/P-X/.provenance.json, and calls
  run_capability_gates("P-X", repo_root, "m") again
Then calls.jsonl holds exactly one bundle

Given the same steps with the header line "# hotdocs-criterion: sha256:0000"
When they run
Then calls.jsonl holds two bundles
```
