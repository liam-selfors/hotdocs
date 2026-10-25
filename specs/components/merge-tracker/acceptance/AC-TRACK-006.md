# AC-TRACK-006

Covers: R-TRACK-006
Kind: compiled

```gherkin
Given several tracking records already written under .hotdocs/tracking/
When a direct DuckDB query (SELECT * FROM read_json('.hotdocs/tracking/*.json'))
  is run, with no use of this component's own CLI or library at all
Then it returns every record correctly, with no transformation or
  ingestion step required beyond that one query
```
