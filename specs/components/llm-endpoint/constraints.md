# LLM Endpoint — Non-Functional Constraints

- **Deterministic resolution, not responses.** Resolution
  (`R-ENDPOINT-002`) is a function of the identifier and configuration;
  two identical `complete()` calls MAY return different text.
