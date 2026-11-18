---
id: arch-test-author-output
title: Test-Author File Content
status: draft
owners: [pipeline-team]
depends_on: []
---

# Test-Author File Content

## Purpose

The exact text of the test file `test-author`'s `author_test` returns,
writes and caches, stated once where every criterion's test author sees
it, so that a test comparing that text with what a mock model replied
knows what to expect (`D320`).

## Rules

**The extracted content.** The model's content is the text between the
`-----BEGIN FILE <nonce>-----` line and the `-----END FILE <nonce>-----`
line: one line break directly after the BEGIN marker and one directly
before the END marker are not part of it, and nothing else is removed
or added. A mock replying
`"-----BEGIN FILE " + n + "-----\nimport x\n-----END FILE " + n + "-----"`
has the content `"import x"`.

**The file content.** The content of `TestAuthoringResult`'s `file`,
the text of the file written under `repo_root`, and the content stored
in `cache-manager` are all the same text: the header line
`# hotdocs-criterion: sha256:<hex>` (`R-AUTHOR-028`), `"\n"`, then the
extracted content. When the extracted content's first line already
begins `# hotdocs-criterion:`, that line is dropped first. A result
read from the cache gets the same treatment, so a cached entry written
without a header comes back with one.

**Comparing in a test.** The header depends on the bundle, so a test
comparing a returned, written or cached content with a mock's reply or
a pre-populated cache entry compares the text after the header line:

    def body(content):
        first, _, rest = content.partition("\n")
        return rest if first.startswith("# hotdocs-criterion:") else content

and asserts `body(content) == expected`, with `expected` the extracted
content as defined above.
