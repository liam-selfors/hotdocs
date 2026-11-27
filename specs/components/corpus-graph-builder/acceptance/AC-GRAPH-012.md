# AC-GRAPH-012

Covers: R-GRAPH-008
Kind: generated-test

```gherkin
Given a corpus whose component comp-a has owners [équipe]
When build_corpus_graph runs and to_json_bytes() is called
Then the bytes equal (json.dumps(graph.to_dict(), sort_keys=True,
  indent=2, ensure_ascii=True) + "\n").encode("utf-8"), and contain
  "\\u00e9quipe" and no "é"
```
