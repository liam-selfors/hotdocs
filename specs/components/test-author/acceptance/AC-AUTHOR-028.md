# AC-AUTHOR-028

Covers: R-AUTHOR-028
Kind: generated-test

```gherkin
Given a bundle for comp-foo whose criterion_text is
  "Given a\nWhen b\nThen c" and whose requirement_text is "R-X-1 MUST c",
  a test-probe stand-in returning ok true, and a mock model replying
  with a marked file whose content is "import x"
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the result's file content, and the text of the file written at
  <tmp>/<file path>, are both "# hotdocs-criterion: sha256:" followed by
  the lowercase hex SHA-256 of "Given a\nWhen b\nThen c\nR-X-1 MUST c"
  (UTF-8), a newline, then "import x"

Given the same bundle, a fresh repo_root, a test-probe stand-in
  returning ok true, and a mock model whose content is
  "# hotdocs-criterion: sha256:0000\nimport x"
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the result's file content has exactly one line starting
  "# hotdocs-criterion:", its first, carrying the correct hex

Given a repo_root where that first call already ran
When author_test is called again with a mock model that must never be
  called
Then cache_hit is true and the result's file content begins with the
  same correct header line
```
