# AC-AUTHOR-030

Covers: R-AUTHOR-030
Kind: generated-test

```gherkin
Given a test-probe stand-in returning ok true, and a mock model counting
  its calls and replying with a marked file whose content is "import x"
  on the first call and "import y" on the second
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called, the written file is deleted, and author_test is called
  again with the same bundle, model, seed and repo_root
Then the model was called twice, both results have cache_hit false,
  the second result's file content after its first line is "import y",
  and <tmp>/.hotdocs/cache/ does not exist
```
