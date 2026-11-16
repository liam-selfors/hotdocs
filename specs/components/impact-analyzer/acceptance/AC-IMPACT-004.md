# AC-IMPACT-004

Covers: R-IMPACT-004
Kind: generated-test

```gherkin
Given VAR-CACHE-STORE-URL changed, and comp-cache-manager has
  uses_var: [VAR-CACHE-STORE-URL]
When hotdocs impact --changed VAR-CACHE-STORE-URL runs
Then the report's impacted list contains comp-cache-manager with reason
  "transitive-var" and via "VAR-CACHE-STORE-URL"
```
