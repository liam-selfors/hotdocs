# AC-RUNENV-007

Covers: R-RUNENV-007
Kind: generated-test

```gherkin
Given testing.md's component with its fake driver (drivers: [fake]),
  except that the fake session's close() also writes the bytes b"png1"
  to <work_dir>/screenshots/final-1.png, the files
  <repo_root>/.hotdocs/screenshots/foo/old/x.png and
  <repo_root>/.hotdocs/screenshots/foo/test_shot/stale.png left from
  before, and
  a test file test_shot.py that uses the fake_session fixture
When env = prepare("comp-foo", repo_root) and test_shot.py is run with
  pytest as testing.md states, once with
  env.env_for(repo_root / "gen" / "foo") and once with
  env.env_for(<another temporary directory>)
Then prepare and both env_for calls leave .hotdocs/screenshots/
  unchanged; env_for(repo_root / "gen" / "foo") holds HOTDOCS_SCREENSHOTS
  equal to str(<repo_root resolved>/.hotdocs/screenshots/foo) and the
  other env_for result holds no HOTDOCS_SCREENSHOTS key; after the
  first run <repo_root>/.hotdocs/screenshots/foo/test_shot/ holds
  exactly final-1.png, holding b"png1" (stale.png is gone), while
  foo/old/x.png is still there; and the second run changes nothing under
  <repo_root>/.hotdocs/screenshots/
```
