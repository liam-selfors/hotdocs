# Config/Env Variable Declarations

One file per parameter: `name`, `required` | `optional`, `type`,
`description`, `sensitivity` (`secret` | `non-secret`).

There is no `value` field in this schema — not a convention to leave it
blank, it has nowhere to go. A `sensitivity: secret` declaration additionally
cannot carry an `example` or `default` field.

See `SPEC_GUIDELINES.md` §3.3 and §10 (secrets).

- **`VAR-ANTHROPIC-API-KEY`** (secret, required)
- **`VAR-SECOND-MODEL-API-KEY`** (secret, optional)
- **`VAR-CACHE-STORE-URL`** (non-secret, required)
- **`VAR-COMPLIANCE-WEBHOOK-URL`** (non-secret, optional)
