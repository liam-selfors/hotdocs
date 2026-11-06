# R-SECRET-012

**R-SECRET-012** — A finding MUST be suppressed only by an exact entry in
  `<repo_root>/.secret-allowlist.json`, and by nothing else. The file is
  scanned like every other file (`R-SECRET-001`), never exempted. It is
  a JSON object with exactly the keys `version` (the integer `1`) and
  `entries` (a list). Each entry has exactly `file`, `type`,
  `hashed_secret`, and `reason`:

  - `file` — a repo-relative path of `A-Z a-z 0-9 _ . / -` only, with no
    leading `/` or `..` segment: never a pattern;
  - `type` — a finding's `rule_id`;
  - `hashed_secret` — `"sha1:"` plus 40 lowercase hex digits, the SHA-1
    of the secret;
  - `reason` — `"planted-fixture"`, valid only for a `file` under
    `verification/` or `specs/`, or `"public-constant"`, valid only for
    `type` `"Hex High Entropy String"`.

  A finding is suppressed iff some entry matches its `file`, type, and
  `"sha1:"` plus its secret's SHA-1, all exactly, and is then listed in
  `allowed`; an entry matching nothing goes in `unused_allowlist_entries`
  and never blocks.

  **Sealed.** An otherwise valid file with no entries needs no seal; one with entries is honored only if
  `sha256:` plus the SHA-256 hex of its exact bytes equals the
  `allowlist_sha256` frontmatter value of the highest-numbered
  `specs/decisions/D<N>.md` that is `ratified` and has that key. With no
  such decision or another hash it is invalid (below): an edit is inert
  until a new decision records its hash (`D195`).

  **Fail closed.** An absent file allows nothing. A file that is not
  valid JSON, has any other key, has any entry breaking a rule above, or
  is unsealed invalidates the **whole** allowlist: no entry is honored,
  every finding is reported, and one extra match is added with `rule_id`
  `"allowlist-invalid"`, `risk_tier` `"high"`, `file`
  `".secret-allowlist.json"`, `line` `1` (`D168`).
