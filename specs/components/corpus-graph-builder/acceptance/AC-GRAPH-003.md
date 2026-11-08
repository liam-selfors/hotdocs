# AC-GRAPH-003

Covers: R-GRAPH-003
Kind: generated-test

```gherkin
Given comp-a with sealed: true, gen/a/.overrides.json holding ["x.py"],
  and verification/a/.provenance.json holding {"spec_bundle_hash":
  "sha256:abc", "generated_at": "2026-11-08T00:19:53Z",
  "verification_report": {"component_id": "comp-a", "overall": "pass"}},
  comp-b with no manifest, and comp-big whose component.md body is the
  word "word" 4001 times
When build_corpus_graph runs
Then comp-a has verification {"component_id": "comp-a", "overall":
  "pass"}, provenance {"spec_bundle_hash": "sha256:abc", "generated_at":
  "2026-11-08T00:19:53Z"}, size_status "ok", sealed true and
  pinned_overrides ["x.py"]; comp-b has verification null, provenance
  null, sealed false and pinned_overrides []; comp-big has size_status
  "over"; and to_json_bytes() does not raise
```
