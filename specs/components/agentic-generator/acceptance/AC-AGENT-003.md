# AC-AGENT-003

Covers: R-AGENT-003
Kind: generated-test

```gherkin
Given a generator stand-in and a loop stand-in whose script is:
  write_file "work/a.py" with content "x = 1"; read_file "work/a.py";
  read_file "/etc/hosts"; read_file "work/../bundle/01-spec.md";
  read_file "secrets/k"; write_file "work/big.py" with 524289 "a"
  characters; delete_file "work/a.py"; read_file "work/a.py"; a call
  named "shell"; read_file with no path; finish with summary "done";
  write_file "work/b.py" with no content
When generate_agentic is called
Then the recorded results are, in order: "wrote work/a.py"; "x = 1";
  three errors starting "path not allowed:"; an error naming the size
  limit; "deleted work/a.py"; an error result; an error starting
  "bad call:"; an error starting "bad call:"; "finished"; and the error
  "already finished"
```
