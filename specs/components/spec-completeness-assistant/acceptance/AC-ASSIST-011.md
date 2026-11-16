# AC-ASSIST-011

Covers: R-ASSIST-011
Kind: generated-test

```gherkin
Given a fake tool root <t> holding a byte-for-byte copy of this
  component's module (read from the imported module's __file__) at
  <t>/gen/spec-completeness-assistant/spec_completeness_assistant.py,
  stand-ins for spec-linter (no findings), impact-analyzer (blast
  radius comp-tool) and spec-bundle-assembler under <t>/gen/, and a
  repo_root with no gen/ directory
When that copy, loaded by file path, runs assist(["R-FOO-001"], repo_root)
Then predicted_blast_radius is ["comp-tool"]

Given the same, plus a repo_root/gen/impact-analyzer/ stand-in whose
  blast radius is comp-mine
When the copy runs assist(["R-FOO-001"], repo_root)
Then predicted_blast_radius is ["comp-mine"]
```
