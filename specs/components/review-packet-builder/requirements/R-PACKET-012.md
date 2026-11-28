# R-PACKET-012

**R-PACKET-012** — `main(argv)` MUST implement `interface/cli.md`
  exactly: `hotdocs review-packet build --changed=<spec-id>...
  [--repo-root=<dir>] [--format=markdown|json]`. Exit `0` once a
  packet is built, exit `1` when a required upstream result was
  missing, any exception `provenance-tracker`'s `check_readiness`
  raises included (such as its `ValueError` for a capability needing a
  fresh run, `D288`), printing its message, exit `2` on any usage error (no subcommand, no `--changed`,
  an invalid `--format`). `--format=json` MUST print the packet as
  `json.dumps(packet, indent=2, sort_keys=True)`, and every JSON value
  in the markdown is dumped with `sort_keys=True`; the default/`--format=markdown` MUST print the human-readable
  rendering actually posted on a PR.

  **The markdown rendering's own content is normative, not left to
  guesswork**: the "## Exemption
  Changes" section MUST always render both a `**Sealed:**` and a
  `**Pinned Overrides:**` bold-labeled line (never an actual `###`
  sub-heading), even when one list is empty — never
  omitting the label just because its own list has no entries.
  The "### License Scan"/"### Secret Scan" sub-sections MUST render
  each flagged entry's own `result` content (e.g.
  `json.dumps(entry["result"])` or an equivalent human-readable
  rendering of its real fields) — never a bare status word like
  `"blocked"`/`"flagged"` standing in for the actual flagged detail a
  reviewer needs to act on.

  **"## Verification Results" and "## Capability Scenarios" MUST
  render each entry as a plain, flat line directly under that one
  section heading — `- <component-id>: <json or summary>` — never a
  nested per-entry sub-heading** (e.g. never `### comp-foo`,
  `### P-ZERO-EDIT`). A per-entry sub-heading is indistinguishable
  from the section's own boundary to a heading-boundary parse.
  "## Provenance Hit Status" renders one line per component,
  `- <component-id>: hit=<true|false>`.
