# R-GATE-003

**R-GATE-003** — The number of generation attempts and the feedback each
  carries are `generation-loop`'s (`D310`): this component MUST NOT call a
  generator itself, retry `run_attempts`, or derive feedback. Its result's
  `attempts` is the loop's `attempts` list unchanged, and `generation_result`
  and `verification` are the loop's last.
