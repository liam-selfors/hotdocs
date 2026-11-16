# AC-ASSIST-004

Covers: R-ASSIST-004
Kind: llm-judge

```gherkin
Given a draft change that adds a requirement with no acceptance criterion
  yet
When assist runs with a model configured
Then completeness_score reflects that gap and completeness_rationale names
  the specific missing criterion
```
