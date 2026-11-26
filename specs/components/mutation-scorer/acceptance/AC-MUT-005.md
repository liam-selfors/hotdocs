# AC-MUT-005

Covers: R-MUT-005
Kind: generated-test

```gherkin
Given the fake kind declared, its strength_sites raising
  ValueError("bad site"), and one passing test
When score is called
Then it returns with mutation_score None and mutation_error
  "fake adapter failed: ValueError: bad site"
```
