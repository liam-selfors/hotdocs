# R-GEN-011

**R-GEN-011** — This component MUST NOT implement its own retry-with-backoff
  logic around an `llm-endpoint` call — `llm-endpoint`'s own bounded-call
  guarantee (`R-ENDPOINT-004`, D30) is the right source of truth for "how
  long is reasonable," not a number this component invents, and not a
  loop this component adds on top. A single call either succeeds, or
  comes back as `model_call_error` (R-GEN-008) exactly once — there is no
  internal attempt loop to exhaust first.

  **Resolves the retry/timeout open question by making the retry mechanism
  someone else's job, deliberately:** a transient failure's recovery path
  is re-running the merge (R-MERGE-017), not a hidden retry loop inside a
  single `generate()` call. This is not a missing feature — `generator`
  never caches a failed call (R-GEN-006 only writes on success), so a
  re-run after any failure, transient or not, naturally only re-attempts
  the components that actually failed; everything that already succeeded
  is a cache hit, at no cost. Building retry-with-backoff into this
  component would duplicate a recovery path that already exists one layer
  up, for free, and would hide failures from the batch-level visibility
  R-MERGE-017 depends on.

  This is **not** `merge-orchestrator`'s best-of-k retry loop (D3,
  R-MERGE-005) — that retries *generation itself*, with a new seed,
  because a prior attempt's *code* failed verification. This requirement
  is about infrastructure-level call failures, before any code was ever
  produced to verify.
