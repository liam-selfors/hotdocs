# R-MERGE-006

**R-MERGE-006** — If all `k` samples fail to produce a passing candidate
  — whether by `model_call_error`, by failing verification, or any mix
  of the two across the `k` attempts — the merge MUST be blocked for that
  component — retries exhausted, not silently accepted. The reason
  recorded for the block MUST distinguish which of the `k` attempts, if
  any, actually reached verification and failed it, versus which never
  produced a candidate at all — both exhaust the same retry budget, but
  they are different facts for a human reading the block reason to know.
