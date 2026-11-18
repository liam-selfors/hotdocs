# AC-AUTHOR-012

Covers: R-AUTHOR-012
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is {},
  and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains the line
  "- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`."
  and the line
  "- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text."
```
