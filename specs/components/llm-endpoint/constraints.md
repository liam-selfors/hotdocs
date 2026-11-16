# LLM Endpoint — Non-Functional Constraints

- **Deterministic resolution, not responses.** Resolution
  (`R-ENDPOINT-002`) is a function of the identifier and configuration;
  two identical `complete()` calls MAY return different text, and caching
  that is each caller's concern through `cache-manager`.
- **The one component that reaches the network** for a model call, with
  the standard library only, no retry and a bounded wait
  (`R-ENDPOINT-004`).
- **Credentials stay here** (`R-ENDPOINT-005`): `hotdocs.toml` names a
  variable, never holds a key.
- **The call log is not a gate input.** `.hotdocs/calls/` is read by
  people and tools afterwards, never by a pass/fail decision
  (`SPEC_GUIDELINES.md` §1).
