# AC-LICENSE-015

Covers: R-LICENSE-012
Kind: generated-test

```gherkin
Given gen/foo/foo.py, and a corpus (via VAR_LICENSE_CORPUS_PATH) whose
  one entry holds every 9-token window hash of foo.py, so a scan of
  comp-foo scores 1.0 and is blocked
And then gen/foo/.provenance.json holding 3000 words of unrelated
  prose, gen/foo/.overrides.json holding {}, and
  gen/foo/__pycache__/foo.cpython-314.pyc and gen/foo/.cache/x.py each
  holding 3000 words of unrelated prose are added
When scan("comp-foo", repo_root) is called
Then blocked is true and similarity_score is 1.0, as before they were
  added

Given gen/foo/foo.py and gen/foo/static/app.js holding 300 words of
  unrelated prose, the corpus holding
  every window hash of foo.py alone
When scan("comp-foo", repo_root) is called
Then similarity_score is below 1.0: a declared asset is content
```
