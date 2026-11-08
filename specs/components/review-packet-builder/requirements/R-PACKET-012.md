# R-PACKET-012

**R-PACKET-012** — `main(argv)` MUST implement `interface/cli.md`
  exactly: `hotdocs review-packet build --changed=<spec-id>...
  [--repo-root=<dir>] [--format=markdown|json]`. Exit `0` once a
  packet is built, exit `1` when a required upstream result was
  missing, exit `2` on any usage error (no subcommand, no `--changed`,
  an invalid `--format`). `--format=json` MUST print the packet as
  `json.dumps(packet, indent=2, sort_keys=True)`, and every JSON value
  in the markdown is dumped with `sort_keys=True`; the default/`--format=markdown` MUST print the human-readable
  rendering actually posted on a PR.

  Found via mutation testing, not a behavioral test failure (same
  shape as `R-PROV-015`/`D130`, `R-DRIFT-005`): every acceptance
  criterion so far exercises `build_review_packet` directly as a
  library call, none through `main()` or its markdown renderer —
  `interface/cli.md` documents the CLI but no requirement or
  acceptance criterion ever covered it.

  **The markdown rendering's own content is normative, not left to
  guesswork** — prose alone has already proven insufficient twice for
  this exact rendering (`D145`'s own retry): the "## Exemption
  Changes" section MUST always render both a `**Sealed:**` and a
  `**Pinned Overrides:**` bold-labeled line (never an actual `###`
  sub-heading — `D152`'s own correction, after a `###` sub-heading
  sitting immediately after `## Exemption Changes` with no
  intervening content repeatedly broke a generated test's own
  "find the next heading" section-boundary parse, the identical
  ambiguity the "## Verification Results"/"## Capability Scenarios"
  fix below already closed), even when one list is empty — never
  omitting the label just because its own list has no entries, the
  same "present, explicitly empty, never omitted" convention
  `R-PACKET-005` already states for `compliance_flags`.
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
  `### P-ZERO-EDIT`). A per-entry sub-heading makes a per-entry id
  indistinguishable, by any generic heading-boundary parse, from the
  section's own content boundary — found after this exact ambiguity
  repeatedly broke a generated test's own section-extraction helper
  across several real rounds. Flat lines (or bold labels) under one
  fixed heading, the same shape "## Residual Risk" and the corrected
  "## Exemption Changes" above both use, removes the ambiguity
  entirely.
