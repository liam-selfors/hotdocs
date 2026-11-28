# R-AUTHOR-009

**R-AUTHOR-009** — The prompt MUST instruct the model to wrap its test
  file's content exactly as:

  ```
  -----BEGIN FILE <nonce>-----
  <the complete, exact test file content, verbatim>
  -----END FILE <nonce>-----
  ```

  with `<nonce>` a fresh, per-call random value in the instruction
  and the extraction regex (`D38`). The instruction MUST also say that
  the two marker lines use exactly this nonce, and that a test needing
  markers in a stand-in model's reply builds them from the nonce it reads
  when it runs, never from this one (`D389`). MUST also state the model
  has no tool/file access and must answer from the bundle alone.

  `author_test` MUST extract strictly from between the markers,
  discarding anything outside (fence, narration, preamble/postamble).
  A reply with no matching BEGIN/END pair is rejected and repaired as
  `R-AUTHOR-027` states. When the last reply still has none, the
  result's `model_call_error` is category `missing_file_markers` with
  message `model reply held no matching BEGIN/END FILE markers; reply
  began: <r>`, `<r>` being `repr()` of the reply's first 200 characters,
  its `file` is null, and nothing is written to disk.

