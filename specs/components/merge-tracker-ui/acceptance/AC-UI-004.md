# AC-UI-004

Covers: R-UI-004
Kind: generated-test

```gherkin
Given the rendered page's source
When inspected for any reference to specs/, gen/, verification/, or
  corpus-graph.json
Then none exists — .hotdocs/tracking/ is the only data source queried
```
