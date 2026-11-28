# R-KCSS-006

**R-KCSS-006** — `run("contrast", [a, b])` and
`run("contrast", [a, b, "dark"])` MUST return a `float`, the contrast
ratio of the colour tokens named `a` and `b` as
`specs/architecture/asset-kind-css.md` "Running criteria" states:
values from `run("tokens", [])`, or for `"dark"` that dict updated with
`run("tokens", ["dark"])`; a name absent raises
`AssetError("no token <name>")`, a value not matching
`^#[0-9a-fA-F]{6}$` raises `AssetError("not a #rrggbb colour: <name>")`,
`a` checked before `b`. The result is `round(ratio, 2)`, and the order
of `a` and `b` does not change it.
