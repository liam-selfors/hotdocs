# AC-SECRET-006

Covers: R-SECRET-006
Kind: generated-test

```gherkin
Given the installed detect-secrets package has version V
  (importlib.metadata.version("detect-secrets"))
When a full scan runs
Then the result's gate_version is exactly
  "secret_scanner@3.1.0+detect-secrets." followed by V

Given a stand-in cache-manager already holding a result stored under
  the same spec_bundle_hash and gate_inputs_hash but a different
  gate_version
When a full scan runs
Then the stored result is not reused and a fresh scan is performed
```
