# AC-AGENT-005

Covers: R-AGENT-005
Kind: generated-test

```gherkin
Given a generator stand-in and a loop stand-in whose script writes
  "work/widget_maker/__init__.py" with "A = 1" and
  "work/widget_maker/core.py" with "B = 2", then calls finish, and which
  returns transcript [{"role": "user", "content": "p"}], turns 3 and
  tool_calls 3
When generate_agentic(bundle for comp-widget-maker with spec_bundle_hash
  "sha256:h", "m", ["R-W-1"], repo_root=<tmp>) is called
Then the result has files {"widget_maker/__init__.py": "A = 1",
  "widget_maker/core.py": "B = 2"}, no model_call_error, mode "agentic",
  cache_hit false, prompt_version "agent-v1", retry_feedback ["R-W-1"],
  spec_bundle_hash "sha256:h", turns 3, tool_calls 3, transcript_sha256
  "sha256:" plus the SHA-256 of json.dumps of that transcript with
  sort_keys, and write_files was called once with those files

Given the script instead writes only "work/notes.py" before finish
When generate_agentic is called
Then model_call_error's category is "missing_module" and write_files
  was never called

Given the bundle's hint_code is {"x.py": "1"} and the first script
When generate_agentic is called
Then the result has files {"widget_maker/__init__.py": "A = 1",
  "widget_maker/core.py": "B = 2"} (what the script wrote, not
  hint_code) and write_files was never called
```
