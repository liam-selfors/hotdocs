# R-GEN-008

**R-GEN-008** — A model-call error, as `llm-endpoint` reports it
  (`R-ENDPOINT-004`, `D18` — network, auth, rate-limit, or timeout) MUST be
  distinct from generated code failing verification. Both block the merge
  (`R-GATE-004`), but a human choosing a re-run or a spec fix (`D3`) needs
  to know whether a candidate was produced.

  A response parsing to no files produced none:
  `model_call_error` is `{"category": "empty_response", "message": ...}`
  and nothing is written or cached. The message is
  `the model reply contained no files; it began:`, a newline, and the
  reply's first 4000 characters, then, for a longer reply, a newline and
  `[<n> more characters]`; for a reply of only whitespace it is
  `the model reply was empty` (`D321`).
