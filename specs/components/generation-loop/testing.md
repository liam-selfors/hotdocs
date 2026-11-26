# Testing generation-loop

All are `kind: generated-test`, with stand-ins for every dependency.

Test fixtures: each dependency is a stand-in module at
`<repo_root>/gen/<slug>/<module>.py` (`generator/generator.py`,
`agentic-generator/agentic_generator.py`, `surface-checker/surface_checker.py`,
`verifier-orchestrator/verifier_orchestrator.py`, `test-author/test_author.py`,
`llm-endpoint/llm_endpoint.py`) providing the names above and recording
each call, with its arguments, to a file.
