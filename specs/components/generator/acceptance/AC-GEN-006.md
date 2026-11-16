# AC-GEN-006

Covers: R-GEN-006
Kind: generated-test

```gherkin
Given an empty cache and a mock model that returns a complete reply
When generate is called
Then the result has files, and cache-manager holds nothing under the
  R-GEN-005 key for that bundle, retry_feedback and model

Given that result
When commit_cache(result, repo_root) is called
Then cache-manager holds a result under that key, and a second generate
  call with the same inputs is a cache hit that never calls the model

Given a result with a model_call_error
When commit_cache(result, repo_root) is called
Then nothing is written to cache-manager
```
