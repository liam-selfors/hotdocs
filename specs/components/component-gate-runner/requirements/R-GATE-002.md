# R-GATE-002

**R-GATE-002** — On a miss, MUST call `spec-bundle-assembler`'s cold-mode
  `assemble`, then `generation-loop`'s `run_attempts` once with that
  bundle and its own `model`, `seed`, `llm_backend`, `retry_feedback`,
  `max_attempts`, `mode` and `allow_unisolated_exec`, exactly as
  `interface/library.md` states. For a sealed component (`R-GATE-007`)
  it MUST instead obtain `verify`'s closures from `generation-loop`'s
  `make_closures`, passing its own `model`, `seed`, `repo_root` and
  `llm_backend` unchanged, and pass the returned `test_author` and
  `judge` to `verify` as that document states, never building a
  closure itself. This component does its own wiring
  (`D86`): its parameters are the only place a model identifier enters.
