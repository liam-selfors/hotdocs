# AC-GQE-009

Covers: R-GQE-001
Kind: generated-test

```gherkin
Given a repo root with one component and two decision records: D1,
  whose frontmatter has the scalar line "supersedes: D2" (a single id,
  never a list), and D2, whose status is "deprecated"
When load_views runs
Then nodes contains a row for each decision, both kind "decision", and
  edges contains exactly the row (D1, D2, "supersedes")
```
