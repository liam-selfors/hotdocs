# AC-PROVCHECK-011

Covers: R-PROVCHECK-007
Kind: generated-test

```gherkin
Given a repo_root with specs/components/foo/component.md whose
  frontmatter has "sealed: true", "source_path: pipeline/foo/", and
  "owners: [pipeline-team, alice]"; pipeline/foo/a.py containing "A=1\n"
  and pipeline/foo/sub/b.py containing "B=2\n"; and a faked
  gen/verifier-orchestrator/verifier_orchestrator.py defining
  GATE_VERSION = "verifier-orchestrator@2.0.0"
When current_sealed_key("comp-foo", repo_root) is called
Then owners is ["pipeline-team", "alice"], source_path is
  "pipeline/foo/", verifier_version is "verifier-orchestrator@2.0.0",
  and source_hash equals "sha256:" plus the SHA-256 the test itself
  computes over b"a.py" + NUL + b"A=1\n" + NUL + b"sub/b.py" + NUL +
  b"B=2\n" + NUL

Given pipeline/foo/__pycache__/x.pyc and pipeline/foo/.sealed-provenance.json
  are added, with any content
When current_sealed_key is called again
Then source_hash is unchanged

Given pipeline/foo/a.py is changed to "A=2\n"
When current_sealed_key is called
Then source_hash differs from before

Given a component whose frontmatter has "sealed: false", and another
  whose component.md does not exist
When current_sealed_key is called for each
Then each returns None

Given a sealed component whose frontmatter has no owners line, or
  "owners: [Alice]", or no source_path line
When current_sealed_key is called
Then it raises ValueError
```
