---
id: arch-test-author-fixtures
title: Test-Author Fixtures
status: draft
owners: [pipeline-team]
depends_on: []
---

# Test-Author Fixtures

## Purpose

How a test of `test-author` calls `author_test`, mocks the model,
stands in for `test-probe` and observes what was written. Every
`AC-AUTHOR-*` criterion's test author sees this document.

## Rules

### Module and call

`test-author` is one module file, `test_author.py`, importable as
`test_author`; a test calls `test_author.author_test(...)`. A
mock-backed test passes any model string, such as `"mock"`, with
`llm_backend` set to its mock. `llm-endpoint` logs each call under the
current directory's `.hotdocs/calls/`, so a test sets the current
directory to its temporary `repo_root` (`monkeypatch.chdir`). Each scenario uses a fresh `repo_root`.

### Bundle

`bundle` is a `CriterionBundle` or any mapping with its keys; a test
passes a plain dict, such as `{"component_id": "comp-widget-maker",
"criterion_id": "AC-WIDGET-MAKER-001", "covers": "R-WIDGET-MAKER-001",
"criterion_text": "...", "requirement_text": "...", "interface": "...",
"glossary": "", "dependency_interfaces": {}}`. A missing
`dependency_interfaces` means `{}`, a missing `module_names` means none,
and a missing `interface` or `glossary` means `""`.

### Reply format and the nonce

Every prompt, repair prompts included, ends with a reply-format
instruction naming the markers literally, `-----BEGIN FILE <n>-----` and
`-----END FILE <n>-----`, each on a line of its own, `<n>` a fresh
`secrets.token_hex(16)` nonce (32 lowercase hex characters). A repair
prompt holds the original prompt, with its old nonce, before its own
instruction, so a mock takes `<n>` as the last match of
`-----BEGIN FILE ([0-9a-f]{32})-----` in the prompt
(`re.findall(...)[-1]`). A mock replies `-----BEGIN FILE <n>-----`, a
newline, the file, a newline, then `-----END FILE <n>-----`.

The extracted file is the text after the newline that ends the BEGIN
line, up to but not including the newline that precedes the END line,
otherwise unmodified: the reply
`-----BEGIN FILE <n>-----\nGOOD\n-----END FILE <n>-----` yields `GOOD`,
and a file `import x\n` is sent as `...-----\nimport x\n\n-----END...`.
That exact string is what `probe` receives as `test_source`, with no
header line; `author_test` applies no other check to it before `probe`.

### The `test-probe` stand-in

A test replaces `test-probe` with a stand-in at
`<repo_root>/gen/test-probe/test_probe.py` defining
`probe(test_source, criterion_bundle, module_name, *, timeout=60.0)`
that returns an object with `ok` (bool), `findings` (a list of dicts
with `kind`, `severity`, `line`, `message`) and `to_dict()`. A stand-in
records its calls by appending to a file the test controls.

### Result and written file

`author_test` returns a `TestAuthoringResult` dataclass with the fields
of `interface/data/TestAuthoringResult.md`, in that order; `file` is
`None` or a plain dict with exactly the keys `path` and `content`. A
test reads each field with dual dict-or-attribute access.

An accepted test is written to `<repo_root>/<file.path>`, `file.path`
relative to `repo_root`:
`verification/<slug>/generated-test/<criterion test filename>`, so
`AC-FOO-003` of `comp-foo` is
`verification/foo/generated-test/test_ac_foo_003.py`. Its
`content` is one header line, `# hotdocs-criterion: sha256:<hex>`, a
newline, then the accepted test exactly as probed. `<hex>` is
the SHA-256 of `json.dumps({k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` encoded UTF-8, as
`specs/architecture/test-reuse.md` defines it (`D341`), 64 lowercase hex
characters, never taken from the model's content; a missing `testing`
key counts as `""`. When the probed test's first line begins
`# hotdocs-criterion:`, that line and its newline are dropped before the
header is prepended.

`author_test` writes nothing but that file, and only for a test whose
probe passed; it keeps no cache (`R-AUTHOR-030`). "Nothing written"
means no file exists under `<repo_root>/verification/`.
