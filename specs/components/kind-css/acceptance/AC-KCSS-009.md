# AC-KCSS-009

Covers: R-KCSS-007
Kind: generated-test

The calibration pair, on testing.md's `s.css`. A suite is a list of
`(entry, args, expected)`. Strong:
`("tokens", [], {"--c-text": "#1f2328", "--c-bg": "#ffffff", "--c-gap": "8px"})`,
`("tokens", ["dark"], {"--c-bg": "#0d1117"})`,
`("rule", [".card, .panel"], {"padding": "var(--c-gap)", "color": "var(--c-text)"})`,
`("rule", [".card.tone-ok:hover"], {"border-left": "4px solid green"})`.
Weak: its first and third entries only.

```gherkin
Given those fixtures
When, for each site of strength_sites(s.css) in turn, a fresh copy of
  s.css has apply_site applied and each suite is run on the copy through
  asset_runner, a site being killed when some call raises AssetError or
  returns a value != expected
Then each suite passes on s.css unmutated, the strong suite kills 7 of
  7 (100%, at or above the 80% bar), and the weak suite kills exactly 5
  of 7 (71.4%, below it): the survivors are "8: --c-bg removed" and
  "16: border-left removed"
```
