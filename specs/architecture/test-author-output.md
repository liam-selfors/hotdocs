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
writes, stated once where every criterion's test author sees
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
and the text of the file written under `repo_root` are the same text: the header line
`# hotdocs-criterion: sha256:<hex>` (`R-AUTHOR-028`), `"\n"`, then the
extracted content. When the extracted content's first line already
begins `# hotdocs-criterion:`, that line is dropped first.

**Comparing in a test.** The header depends on the bundle, so a test
comparing a returned or written content with a mock's reply compares the text after the header line:

    def body(content):
        first, _, rest = content.partition("\n")
        return rest if first.startswith("# hotdocs-criterion:") else content

and asserts `body(content) == expected`, with `expected` the extracted
content as defined above.

## The CLI (`R-AUTHOR-029`)

`main(argv)` follows `specs/architecture/cli-conventions.md` and
`test-author`'s `interface/cli.md`. Besides the conventions' usage
errors, these are usage errors, each with its exact cause:
`expected <component-id> and <criterion-id>` when the positional
arguments are not exactly two, `missing required --model`,
`--format must be json or text`, and `--seed must be an integer` when
the value is not an optional `-` followed by digits. An unknown
argument's cause is `unknown argument <token>`; a value-taking flag
given last is `<flag> requires a value`. `--seed` defaults to `0`,
`--format` to `text`, `--repo-root` to the current directory.

Otherwise `main` builds the bundle with `spec-bundle-assembler`'s
`assemble_criterion(component_id, criterion_id, repo_root)`, loaded as
every dependency is, calls the module's own `author_test(bundle, model,
seed, repo_root=repo_root)` (looked up at call time, so a test may
replace it), and prints exactly one line to stdout: with `json`,
`json.dumps(dataclasses.asdict(result))`; with `text`,
`<criterion_id>: wrote <file path>` when `model_call_error` is `None`,
else `<criterion_id>: model_call_error <category>: <message>`. It
returns `0` when `model_call_error` is `None`, else `1`.

A CLI test plants a `spec-bundle-assembler` stand-in at
`<repo_root>/gen/spec-bundle-assembler/spec_bundle_assembler.py` whose
`assemble_criterion` returns a fixed dict, replaces `author_test` with
`monkeypatch.setattr(test_author, "author_test", stub)`, and reads
stdout and stderr with `capsys`.
