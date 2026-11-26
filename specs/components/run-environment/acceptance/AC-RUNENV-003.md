# AC-RUNENV-003

Covers: R-RUNENV-003
Kind: generated-test

```gherkin
Given the fake driver declared
When prepare("comp-foo", repo_root) is called
Then ok is true and drivers is [{"name": "fake", "definition_sha256":
  None, "adapter_sha256": <hash of driver_fake.py>, "versions":
  {"fakedrv": "2.0"}, "lockfile_sha256": None}]

Given, separately, the unprovisioned fake driver declared;
  "drivers: [nodrv]"; and the unprovisioned fake kind declared with the
  fake driver
When prepare is called
Then ok is false and failure_message is "fake needs fakedrv >= 3",
  "unknown test driver: nodrv", or "fake needs fakeprog >= 2"
```
