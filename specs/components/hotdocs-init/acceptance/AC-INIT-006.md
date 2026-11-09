# AC-INIT-006

Covers: R-INIT-006
Kind: generated-test

```gherkin
Given a fake tool root and main(["<dir>","--example","--yes"])
When init runs
Then specs/product/slugs.md exists as a copy of the example, an existing example file is never overwritten,
  and the output ends with next steps naming "hotdocs lint", "hotdocs generate comp-slugify", "hotdocs verify", and "QUICKSTART.md"

Given no --example
When init runs
Then the next steps do not mention "comp-slugify"

Given an initialised project (a directory a previous init run set up, so
  .hotdocs-tool.json and hotdocs.toml exist) and main(["<dir>","--reconfigure","--provider","openai","--model","m","--no-test"])
When it runs
Then only hotdocs.toml changed; and with a tool root holding no gen/llm-endpoint/llm_endpoint.py it returns 1

Given a directory holding only specs/ and main(["<dir>","--reconfigure","--provider","openai","--model","m","--no-test"])
When it runs
Then it returns 1 and writes nothing
```
