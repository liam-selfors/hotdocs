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
```
