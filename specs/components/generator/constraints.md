# Generator — Non-Functional Constraints

- **Not deterministic, but bounded.** A fresh model call need not be
  reproducible; a **cache hit** (R-GEN-005) always returns byte-identical
  output for the same key.
- **`retry_feedback` stays bare at every layer.** Prompt construction
  MUST NOT enrich `R-GEN-012`'s `R-id` list with anything, such as
  `acceptance/` text.
- **Defense-in-depth on write paths.** R-GEN-009's check MUST run
  here, before any model call, despite `R-GATE-007`.
- **No silent partial output.** A model-call error MUST leave
  `gen/<component>/` untouched — never a half-written tree.
- **Credential handling.** This component holds no credential;
  `llm-endpoint` does (`D18`). Only `model` (the identifier) is ever
  recorded.
