# AC-KPY-007

Covers: R-KPY-005
Kind: generated-test

```gherkin
Given tmp_path / "environments" / "python" / "requirements.lock"
  holding exactly
  "# pytest==8.3.0\npytest-cov==5.0.0\n-r other.txt\npytester\n"
When provision(tmp_path) is called
Then the result is exactly {"ok": False,
  "reason": "python environment: requirements.lock does not pin pytest",
  "versions": {}, "interpreter": None,
  "lockfile_sha256": "sha256:" + hashlib.sha256(<the lock's bytes>).hexdigest()}
And tmp_path / ".hotdocs" does not exist afterwards

Given tmp_path / ".hotdocs" created as an empty regular file
And the lock holding exactly "--no-index\npytest==99.0.0\n"
When provision(tmp_path) is called
Then ok is False, versions {}, interpreter None, and reason starts with
  "python environment: [Errno 20] Not a directory: "
  (the lock's directory cannot be created; nothing reaches the network)
```
