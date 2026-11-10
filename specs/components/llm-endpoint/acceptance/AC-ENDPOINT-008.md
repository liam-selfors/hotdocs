# AC-ENDPOINT-008

Covers: R-ENDPOINT-008
Kind: generated-test

```gherkin
Given anthropic, openai and gemini, each with its key variable set, and
  ollama, which takes no key, and
  urllib.request.urlopen replaced by a recorder returning that
  provider's documented success reply
When complete("say hi", "<provider>:m", max_tokens=50) is called
Then the recorded request has the method, URL, auth header, and body
  that R-ENDPOINT-008's table gives for that provider, the Gemini key is
  in a header and not the URL, and ModelResponse.text is the table's
  answer — for anthropic the joined text blocks with a thinking block
  before them, for gemini the non-thought parts

Given a hotdocs.toml whose [llm] table is provider "openai-compatible",
  model "m" and base_url "http://h:8000/v1", and no key
When it is called
Then the request goes to http://h:8000/v1/chat/completions with no
  Authorization header and a max_tokens field
```
