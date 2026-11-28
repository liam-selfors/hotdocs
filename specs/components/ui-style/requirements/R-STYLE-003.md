# R-STYLE-003

**R-STYLE-003** — The stylesheet's second rule MUST be
`@media (prefers-color-scheme: dark)` holding one rule, `:root`, that
declares exactly these colour tokens, in this order, and nothing else:

| Token | Value |
| --- | --- |
| `--color-bg` | `#0d1117` |
| `--color-surface` | `#151b23` |
| `--color-text` | `#f0f6fc` |
| `--color-text-muted` | `#9198a1` |
| `--color-border` | `#3d444d` |
| `--color-accent` | `#4493f8` |
| `--color-focus` | `#4493f8` |
| `--color-ok` | `#3fb950` |
| `--color-warn` | `#d29922` |
| `--color-fail` | `#f85149` |
| `--color-neutral` | `#8b949e` |

Every value of `R-STYLE-002` and of this table meets
`specs/architecture/visual-style.md` "Contrast": each text pair at
least 4.5 and each non-text pair at least 3, in both the light values
and the dark values over the light ones.
