# AC-ASSIST-007

Covers: R-ASSIST-007
Kind: generated-test

```gherkin
Given assist is called with no model configured
When it runs
Then lint_findings/predicted_blast_radius/hint_previews are still
  populated, degraded is true, and completeness_score/
  completeness_rationale/redundancy_flags are empty rather than guessed
```
