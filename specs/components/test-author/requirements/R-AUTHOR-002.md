# R-AUTHOR-002

**R-AUTHOR-002** — The `CriterionBundle` MUST NOT include the target
  component's actual `gen/<component>/` source code — only its
  `interface/` contract. This is the same "write against the contract,
  not by reading the implementation" discipline `spec-bundle-assembler`
  already enforces for `generator` (R-ASSEMBLE-001), applied here to
  preserve the independence D4/D5 require of a `generated-test` check.
