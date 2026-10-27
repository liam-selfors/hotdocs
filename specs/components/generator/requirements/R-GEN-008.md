# R-GEN-008

**R-GEN-008** — A model-call error, as `llm-endpoint` reports it
  (`R-ENDPOINT-004`, `D18` — network, auth, rate-limit, or timeout) MUST be
  surfaced as a distinct failure mode from "the model responded but the
  generated code failed verification" — both block the merge for that
  component (`component-gate-runner`'s `R-GATE-004`), but a human deciding whether to just re-run
  or fix the spec first (`D3`) needs to know which one actually
  happened: no candidate was ever produced, versus one was produced and
  found wanting. Conflating them would hide that distinction from
  exactly the person who needs it.
