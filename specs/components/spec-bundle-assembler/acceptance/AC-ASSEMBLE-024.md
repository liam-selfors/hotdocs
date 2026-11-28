# AC-ASSEMBLE-024

Covers: R-ASSEMBLE-017
Kind: generated-test

```gherkin
Given the library's test fixture with comp-foo's frontmatter gaining
  "drivers: [fake]", and <repo_root>/gen/driver-fake/driver_fake.py
  defining guidance() returning {"test_author": "  Fake driver text.  "}
When assemble_criterion("comp-foo", "AC-FOO-001", repo_root) runs
Then its testing ends with "\n## Test driver: fake\n\nFake driver text."
  and assemble's SpecBundle contains no "Fake driver text."

Given specs/architecture/test-driver-nodrv.md (any text), a component
  comp-driver-nodrv built as foo is, with source_path
  legacy/driver-nodrv/, foo's depends_on [comp-driver-nodrv] and
  "drivers: [nodrv]", and no gen/driver-nodrv/ anywhere, so the corpus
  lints clean but the driver has no adapter
When assemble_criterion runs
Then it raises PreconditionFailure with the message
  "unknown test driver: nodrv"
```
