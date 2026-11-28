# AC-LINT-034

Covers: R-LINT-015
Kind: generated-test

```gherkin
Given testing.md's clean corpus written with write_corpus and these
  changes: specs/glossary.md holding "# Glossary", "", "- **Foo** — a
  made thing."; foo's component.md's Definitions body replaced by
  "- **Foo** — a widget the team sells by weight."; and
  interface/cli.md added as testing.md's one-warn edit
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
