# AC-ASSIST-008

Covers: R-ASSIST-008
Kind: generated-test

```gherkin
Given a CompletenessReport with a non-trivial completeness_score
When the report's schema is inspected
Then it exposes fields a calling tool can use to record an accept/override
  decision, without this component itself persisting that decision anywhere
```
