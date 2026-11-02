# R-AUTHOR-009

**R-AUTHOR-009** — The prompt MUST instruct the model to wrap its test
  file's content exactly as:

  ```
  -----BEGIN FILE <nonce>-----
  <the complete, exact test file content, verbatim>
  -----END FILE <nonce>-----
  ```

  with `<nonce>` a fresh, per-call random value in the instruction
  and the extraction regex — same mechanism `generator` already uses
  (`R-GEN-015`, `D38`), for one file. MUST also state the model has
  no tool/file access and must answer from the bundle alone.

  `author_test` MUST extract strictly from between the markers,
  discarding anything outside (fence, narration, preamble/postamble).
  No matching BEGIN/END pair MUST be a distinct authoring failure —
  nothing written to cache or disk, same posture `R-AUTHOR-007`
  states for a `model_call_error`.

