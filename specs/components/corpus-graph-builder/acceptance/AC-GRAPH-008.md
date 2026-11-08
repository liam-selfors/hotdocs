# AC-GRAPH-008

Covers: R-GRAPH-008
Kind: generated-test

```gherkin
Given comp-a and comp-b, comp-a with verification/a/.provenance.json
  holding {"generated_at": "2026-11-08T00:19:53Z",
  "verification_report": {"overall": "pass"}}
When build_corpus_graph runs twice and write_corpus_graph runs twice
Then both to_json_bytes() results are equal, both written files have
  those same bytes, and json.loads of them gives back the generated_at
  string "2026-11-08T00:19:53Z"
```
