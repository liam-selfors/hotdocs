# AC-LINT-018

Covers: R-LINT-018
Kind: compiled

```gherkin
Given a component's depends_on_guarantees lists G-BAR-001, which exists
  under component bar's interface/guarantees/, but "comp-bar" is not
  listed in this component's own depends_on
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-018
  naming comp-bar as the missing dependency
```
