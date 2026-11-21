# R-KJS-007

**R-KJS-007** — `strength_sites(asset_file)` MUST return one
`StrengthSite` per scan token below, in text order:

| Token | Swap |
| --- | --- |
| `===` / `!==` | `!==` / `===` |
| `==` / `!=` | `!=` / `==` |
| `<` / `>=` | `>=` / `<` |
| `>` / `<=` | `<=` / `>` |
| `&&` / `\|\|` | `\|\|` / `&&` |
| name `true` / `false` | `false` / `true` |
| `+` / `-` | `-` / `+` |

`+` and `-` are sites only when the token before them is a number, `)`,
`]`, or a name other than `return`, `typeof`, `void`, `delete`, `throw`,
`new`, `in`, `of`, `instanceof`, `case`, `do`, `else`, `yield` or
`await`; otherwise (`-x` after `=`, `(`, `,`, an operator or one of
those keywords) they are unary and no site. Because the scan reads the
longest operator, `=>`, `++`, `+=`, `<<`, `>>`, `>>>` and the like are
never sites. A file with no sites gives `[]`.
