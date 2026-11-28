# AC-SUPPLY-005

Covers: R-SUPPLY-002
Kind: generated-test

```gherkin
Given each case below
When supply("comp-foo", "AC-FOO-001", repo_root, ...) is called
Then authored and test_authoring are exactly:
  | case                                                      | authored | test_authoring |
  | a current committed test passing its probe                | False    | None           |
  | no committed test and no test_author                      | False    | None           |
  | a stand-in always returning model_call_error auth          | True     | A              |
  | a stand-in returning a file whose probe fails every time  | True     | A              |
  where A is {"model": "m", "seed": 0, "prompt_version": "v1",
  "cache_hit": False}

Given the assembler stand-in's criterion_text "café" and a committed
  test whose first line is the header computed from that bundle by
  testing.md's formula (ensure_ascii=False)
When supply is called with a test_author stand-in
Then author.log does not exist and authored is False
```
