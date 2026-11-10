# AC-LINT-028

Covers: R-LINT-028
Kind: generated-test

```gherkin
Given a fixture glossary with the entry Widget, a live requirement
  citing that entry in the citation form, and another citing the entry
  Gizmo, which the glossary lacks, in the same form
When the linter runs
Then only the second citation gets a R-LINT-028 finding

Given a citation wrapped across two lines, one with a comma before the
  closing quote, one in a different letter case, and one quoting
  "<Term>"
When the linter runs
Then only the different-case citation gets a finding
```
