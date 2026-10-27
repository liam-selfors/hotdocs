# R-AUTHOR-009

**R-AUTHOR-009** — The prompt MUST instruct the model to wrap its test
  file's content exactly as:

  ```
  -----BEGIN FILE <nonce>-----
  <the complete, exact test file content, verbatim>
  -----END FILE <nonce>-----
  ```

  with `<nonce>` a fresh, per-call random value embedded in both the
  instruction and the extraction regex — the same per-call nonce
  mechanism `generator` already uses (`R-GEN-015`, `D38`), applied here
  to exactly one file instead of several. The prompt MUST also state
  explicitly that the model has no tool or file access and must
  produce its answer using only the bundle content given — nothing
  invented or explored about the target component's real implementation.

  `author_test` MUST extract the file content strictly from between
  the markers, discarding anything outside them (a markdown code fence,
  narration, a partial tool-call transcript, or any other preamble/
  postamble a real model response might still include despite the
  instruction above). A response with no matching BEGIN/END pair MUST
  be treated as a distinct authoring failure — nothing written to cache
  or disk — the same "no silent partial output" posture `R-AUTHOR-007`
  already states for a `model_call_error`, extended to cover a
  malformed-but-error-free response.

  **Found only once a real, non-mocked `author_test` call had to
  survive a genuine model response** (`D94`): every `AC-AUTHOR-*`
  criterion is verified against an injected mock backend returning
  clean text directly, so this gap was invisible until `provenance-
  tracker`'s bootstrap exercised this component for real for the first
  time.
