# AC-LINT-034

Covers: R-LINT-015
Kind: generated-test

```gherkin
Given a corpus with no fail-severity finding, at least one warn finding,
  and one Definitions entry naming a glossary term in words that are
  not near-verbatim
When lint(None, repo_root) runs with no judge
Then that entry's R-LINT-015 finding has severity "skipped", and
  hard_failures, warnings and skipped equal the numbers of fail, warn
  and skipped findings, with to_json()'s summary the same three counts

Given the same corpus
When lint(None, repo_root, strict=True) runs
Then hard_failures equals the number of warn findings

Given a judge returning (True, "contradicts the glossary"), then one
  returning (False, "consistent"), then one returning None
When lint runs once with each
Then the entry's R-LINT-015 finding is, in turn, a fail whose to_json()
  includes rationale "contradicts the glossary"; absent; and skipped,
  with no rationale key in its to_json()
```
