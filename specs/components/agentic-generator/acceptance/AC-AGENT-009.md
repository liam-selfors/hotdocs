# AC-AGENT-009

Covers: R-AGENT-003
Kind: generated-test

```gherkin
Given a generator stand-in and a loop stand-in whose script is:
  write_file "work/pkg/a.py" with "A = 1"; write_file "work/pkg/b.py"
  with "B = 2"; list_files "work"; read_file "work/pkg"; write_file
  "scratch/long.txt" with 9000 "y" characters; read_file
  "scratch/long.txt"; write_file "scratch/f001.py" through
  "scratch/f197.py", each with "x = 0"; write_file "scratch/f198.py"
  with "x = 0"; write_file "work/pkg/a.py" with "A = 2"; read_file
  "work/pkg/a.py"; delete_file "work/pkg/b.py"; write_file
  "scratch/f198.py" with "x = 0"; finish with summary "done"
When generate_agentic(bundle for comp-widget, "m", repo_root=<tmp>) is
  called
Then the recorded (text, is_error) pairs are, in order:
  ("wrote work/pkg/a.py", false); ("wrote work/pkg/b.py", false);
  ("work/pkg/a.py\nwork/pkg/b.py", false); ("not found: work/pkg",
  true); ("wrote scratch/long.txt", false); 8192 "y" characters
  followed by "\n[truncated]", false; ("wrote scratch/f<NNN>.py",
  false) for each of the 197 writes; ("too many files: limit 200",
  true); ("wrote work/pkg/a.py", false); ("A = 2", false); ("deleted
  work/pkg/b.py", false); ("wrote scratch/f198.py", false);
  ("finished", false)

Given SANDBOX_EXEC and BWRAP set to "/nonexistent/sandbox" and a script
  that writes "work/widget.py" with "A = 1", calls check_import, then
  finish
When generate_agentic(bundle for comp-widget, "m", repo_root=<tmp>,
  allow_unisolated_exec=True) is called
Then check_import's recorded pair is ("0\n", false) and the result's
  isolation is "unisolated"
```
