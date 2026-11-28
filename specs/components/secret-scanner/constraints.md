# Secret Scanner — Non-Functional Constraints

- **Determinism (full-scan form).** The same repository content,
  allowlist, and `detect-secrets` version MUST give the same result
  (`D30`).
- **No model calls**; no network but the webhook.
