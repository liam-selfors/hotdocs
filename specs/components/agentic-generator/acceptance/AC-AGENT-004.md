# AC-AGENT-004

Covers: R-AGENT-004
Kind: generated-test

```gherkin
Given a generator stand-in, platform macOS with /usr/bin/sandbox-exec,
  and a loop stand-in whose script is: write_file "work/widget.py" with
  "import os\nKEY = os.environ.get('ANTHROPIC_API_KEY')\n"; write_file
  "scratch/test_w.py" with a test asserting widget.KEY is None and that
  socket.create_connection(("1.1.1.1", 80), timeout=3) raises OSError;
  check_import; run_scratch_tests; finish
When generate_agentic(bundle for comp-widget, ...) is called with
  ANTHROPIC_API_KEY set to "k" in the test's environment
Then check_import's result starts "0\n", run_scratch_tests' result
  starts "0\n", and the result's isolation is "sandbox-exec" (a test on
  a platform without sandbox-exec skips this scenario)

Given SANDBOX_EXEC and BWRAP set to "/nonexistent/sandbox"
When generate_agentic is called with the same script
Then check_import's result is the error
  "no OS sandbox available: code is not run" and isolation is "none";
  and with allow_unisolated_exec=True check_import starts "0\n" and
  isolation is "unisolated"

Given repo_root/gen/kind-python/kind_python.py, a stand-in adapter whose
  provision(repo_root) returns ok true, versions {}, lockfile_sha256
  None and interpreter a shell script outside repo_root that appends one
  line to a log file beside it and then runs the test's own
  sys.executable with its arguments, and SANDBOX_EXEC and BWRAP set to
  "/nonexistent/sandbox"
When generate_agentic is called with the same script, that repo_root
  and allow_unisolated_exec=True
Then check_import's result starts "0\n", and the log holds exactly two
  lines, one for check_import and one for run_scratch_tests
```
