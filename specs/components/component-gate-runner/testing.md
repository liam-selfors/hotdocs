# Testing component-gate-runner

## Stand-ins

Every criterion fakes every dependency: a stand-in at
`<repo_root>/gen/<slug>/<module>.py` (`provenance-checker/provenance_checker.py`,
`spec-bundle-assembler/spec_bundle_assembler.py`,
`generation-loop/generation_loop.py`,
`provenance-tracker/provenance_tracker.py`,
`verifier-orchestrator/verifier_orchestrator.py`,
`license-scanner/license_scanner.py`, `secret-scanner/secret_scanner.py`,
`provenance-writer/provenance_writer.py`) providing the names
`interface/library.md` lists and recording each call, with its
arguments, to a file; tests assert on call order, arguments and the
returned `ComponentPipelineResult`. A stand-in may return plain dicts; a
`run_attempts` stand-in returns a dict with `AttemptLoopResult`'s keys
and calls `on_attempt` only when its test says so. Unless a criterion
says otherwise, `current_sealed_key` returns `None`. A CLI test's
`repo_root` also holds `specs/components/<slug>/component.md`
(`specs/architecture/generate-cli.md`).

## The committed manifest

`AC-GATE-011` writes `<repo_root>/gen/foo/.provenance.json` holding
model_pin "m0", prompt_version "v9", retry_feedback null, attempts 2,
attempt_history [{"number": 1, "outcome": "passed"}] and generation
{"mode": "agentic", "generator_version": "g@1", "transcript_sha256":
null, "turns": 4, "tool_calls": 7, "isolation": "seatbelt"}.
