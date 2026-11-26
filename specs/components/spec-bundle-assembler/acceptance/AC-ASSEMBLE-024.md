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

Given "drivers: [nodrv]" with no adapter planted
When assemble_criterion runs
Then it raises PreconditionFailure with the message
  "unknown test driver: nodrv"
```
