# R-STYLE-004

**R-STYLE-004** — After those two, the stylesheet MUST hold exactly these
rules, in this order, each with exactly these declarations in this
order (a value as `specs/architecture/asset-kind-css.md` "Running
criteria" compares it), and no other rule:

| Selector | Declarations |
| --- | --- |
| `body` | `margin: 0`; `padding: var(--space-5)`; `background: var(--color-bg)`; `color: var(--color-text)`; `font-family: var(--font-body)`; `font-size: var(--text-base)`; `line-height: 1.5` |
| `a` | `color: var(--color-accent)` |
| `code, pre` | `font-family: var(--font-mono)`; `font-size: var(--text-sm)` |
| `h1` | `font-size: var(--text-xl)`; `margin: 0 0 var(--space-4)` |
| `h2` | `font-size: var(--text-lg)`; `margin: var(--space-5) 0 var(--space-3)` |
| `.node` | `padding: var(--space-2) var(--space-3)`; `border: 1px solid var(--color-border)`; `border-radius: var(--radius)`; `background: var(--color-surface)` |
| `.tone-ok` | `border-left: 4px solid var(--color-ok)` |
| `.tone-warn` | `border-left: 4px solid var(--color-warn)` |
| `.tone-fail` | `border-left: 4px solid var(--color-fail)` |
| `.tone-neutral` | `border-left: 4px solid var(--color-neutral)` |
| `.edge-depends-on` | `stroke: var(--color-edge-depends-on)` |
| `.edge-realizes` | `stroke: var(--color-edge-realizes)` |
| `.edge-other` | `stroke: var(--color-edge-other)` |
| `.muted` | `color: var(--color-text-muted)` |
| `:focus-visible` | `outline: 2px solid var(--color-focus)`; `outline-offset: 2px` |

The four `tone-` rules come after `.node`, so on an element with both
classes the tone's left border wins over `.node`'s border.
