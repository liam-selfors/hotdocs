# R-GEN-008

**R-GEN-008** — A model-call error, as `llm-endpoint` reports it
  (`R-ENDPOINT-004`, `D18` — network, auth, rate-limit, or timeout) MUST be
  distinct from generated code failing verification. Both block the merge
  (`R-GATE-004`), but a human choosing a re-run or a spec fix (`D3`) needs
  to know whether a candidate was produced.

  A response parsing to no files produced none:
  `model_call_error` is `{"category": "empty_response", "message": ...}`
  and nothing is written or cached.
