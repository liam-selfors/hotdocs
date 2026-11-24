# AC-AUTHOR-028

Covers: R-AUTHOR-028
Kind: generated-test

```gherkin
Given a bundle for comp-foo whose criterion_text is
  "Given a\nWhen b\nThen c", requirement_text "R-X-1 MUST c", interface
  "I", glossary "G" and testing "T",
  a test-probe stand-in returning ok true, and a mock model replying
  with a marked file whose content is "import x"
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the result's file content, and the text of the file written at
  <tmp>/<file path>, are both "# hotdocs-criterion: sha256:" followed by
  the lowercase hex SHA-256 of json.dumps of {"criterion_text",
  "requirement_text", "interface", "glossary", "testing"} with those five
  values, sort_keys=True, ensure_ascii=False and separators (",", ":"),
  encoded UTF-8,
  a newline, then "import x"

Given the same bundle with testing "T2"
When author_test is called with a fresh repo_root
Then the header's hex differs from the first one

Given the same bundle, a fresh repo_root, a test-probe stand-in
  returning ok true, and a mock model whose content is
  "# hotdocs-criterion: sha256:0000\nimport x"
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the result's file content has exactly one line starting
  "# hotdocs-criterion:", its first, carrying the correct hex
```
