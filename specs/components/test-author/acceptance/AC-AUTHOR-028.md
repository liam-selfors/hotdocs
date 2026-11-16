# AC-AUTHOR-028

Covers: R-AUTHOR-028
Kind: generated-test

```gherkin
Given a bundle whose criterion_text is "Given a\nWhen b\nThen c" and
  whose requirement_text is "R-X-1 MUST c", a test-probe stand-in
  returning ok True, and a mock model replying with a marked file whose
  content is "import x\n"
When author_test is called
Then the written file's text is "# hotdocs-criterion: sha256:" followed
  by the hex SHA-256 of "Given a\nWhen b\nThen c\nR-X-1 MUST c" (UTF-8),
  a newline, then "import x\n"

Given the same bundle and a mock model whose content is
  "# hotdocs-criterion: sha256:0000\nimport x\n"
When author_test is called
Then the written file has exactly one line starting
  "# hotdocs-criterion:", and it carries the correct hex
```
