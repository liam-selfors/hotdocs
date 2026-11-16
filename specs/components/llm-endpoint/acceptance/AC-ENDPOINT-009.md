# AC-ENDPOINT-009

Covers: R-ENDPOINT-004
Kind: generated-test

```gherkin
Given each HTTP provider and urlopen replaced by a recorder that
  raises, on its first and only call, HTTP 401, 403, 429, 408, 504, 500,
  a socket timeout, a refused connection, or returns an unreadable body
When complete() is called
Then model_call_error.category is respectively auth, auth, rate_limit,
  timeout, timeout, network, timeout, network, network; the recorder was
  called once; and nothing is raised

Given a provider that needs a key, and no key in the environment
When complete() is called
Then the category is auth and the recorder was never called

Given Gemini replies HTTP 400 saying the API key is not valid
Then the category is auth
```
