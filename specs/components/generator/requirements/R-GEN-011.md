# R-GEN-011

**R-GEN-011** — This component MUST NOT retry an `llm-endpoint` call or
  loop over attempts itself. A single call either succeeds or comes back
  as `model_call_error` (R-GEN-008) exactly once; whether to make
  another attempt, and with what `retry_feedback`, is its caller's
  decision.
