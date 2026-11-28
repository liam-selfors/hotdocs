---
id: arch-visual-style
title: Visual style
status: draft
owners: [pipeline-team]
depends_on: [arch-asset-kind-css]
---

# Visual style

One look for every page `hotdocs` writes (`D386`). The values live in
one generated stylesheet, `comp-ui-style`'s `static/style.css`; this
document states the rules that stylesheet and every page using it
follow. A page implements this document; it never defines a colour,
font or spacing of its own.

## Tokens

The stylesheet declares these custom properties in its top-level
`:root` rule, and no others:

| Group | Tokens |
| --- | --- |
| Colour | `--color-bg`, `--color-surface`, `--color-text`, `--color-text-muted`, `--color-border`, `--color-accent`, `--color-focus`, `--color-ok`, `--color-warn`, `--color-fail`, `--color-neutral`, `--color-edge-depends-on`, `--color-edge-realizes`, `--color-edge-other` |
| Type | `--font-body`, `--font-mono`, `--text-sm`, `--text-base`, `--text-lg`, `--text-xl` |
| Space | `--space-1`, `--space-2`, `--space-3`, `--space-4`, `--space-5`, `--radius` |

Every colour token's value is `#rrggbb`, six lowercase hex digits. The
rule `:root` inside `@media (prefers-color-scheme: dark)` redefines every
colour token, and only colour tokens.

## Contrast

The contrast ratio of two colours is WCAG 2.2's: each channel `v` of
`#rrggbb` becomes `c = v / 255`, then `c / 12.92` when `c <= 0.04045`,
else `((c + 0.055) / 1.055) ** 2.4`; a colour's luminance is
`0.2126 * R + 0.7152 * G + 0.0722 * B` of those; the ratio is
`(lighter + 0.05) / (darker + 0.05)`, rounded to two decimals.

In both the light and the dark values:

- text pairs are at least 4.5: `--color-text`, `--color-text-muted` and
  `--color-accent`, each on `--color-bg` and on `--color-surface`;
- non-text pairs are at least 3: `--color-focus`, `--color-ok`,
  `--color-warn`, `--color-fail`, `--color-neutral` and the three
  `--color-edge-` tokens, each on
  `--color-bg` and on `--color-surface`.

## Tones

A status a page shows is one of four tones, each a class:

| Class | Colour token | Used for |
| --- | --- | --- |
| `tone-ok` | `--color-ok` | `passing`; size `ok` |
| `tone-warn` | `--color-warn` | `missing` |
| `tone-fail` | `--color-fail` | `failing`; size `over` |
| `tone-neutral` | `--color-neutral` | `not-attempted`; size `unknown` |

A tone class sets `border-left: 4px solid var(<its token>)` and nothing
else, so two tones differ in colour alone, and never by colour alone
in meaning: the element also shows the status as text.

## Edges

A drawn graph edge carries one class by its kind: `edge-depends-on` for
`depends_on`, `edge-realizes` for `realizes`, `edge-other` for any other
kind. Each sets `stroke: var(<its --color-edge- token>)` and nothing
else; a script sets the class, never a colour.

## Pages

- A page's only CSS is one `<style>` element, `comp-ui-style`'s
  `style_element()`, written once inside `<head>`. No other `<style>`
  element, no `style="..."` attribute, no `<link rel="stylesheet">`.
- The page loads `ui_style` by path from the tool's own
  `gen/ui-style/ui_style.py`, with
  `importlib.util.spec_from_file_location("ui_style", <that path>)`, the tool being the parent of the nearest
  directory named `gen` above the page module's file: the look is
  `hotdocs`' own, never a project's.
- Classes a page relies on are those `comp-ui-style`'s interface lists;
  a page needing another adds it to `comp-ui-style`, not to itself.
- Every focusable element shows `:focus-visible`'s outline; a page never
  removes it.
- Dark mode follows the reader's `prefers-color-scheme`; a page adds no
  toggle.

## Checking a page

A page's criteria check its look through the browser driver
(`specs/architecture/test-driver-browser.md`): `style(property)` reads
a computed value, `rgb(r, g, b)` for a colour, and `open(...,
color_scheme="dark")` shows the dark values. A criterion compares
computed values with each other and with the ratios above, never with
a token's literal value, so a new colour in `comp-ui-style` regenerates
no page. Pixels and screenshots are for people (`D373`).

## Open questions

None.
