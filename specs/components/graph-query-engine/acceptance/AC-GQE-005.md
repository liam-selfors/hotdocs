# AC-GQE-005

Covers: R-GQE-005
Kind: compiled

```gherkin
Given a component with a committed verification/<component>/.provenance.json
When load_views runs and component_provenance is queried for it
Then the row's fields match that file's own JSON content exactly
```
