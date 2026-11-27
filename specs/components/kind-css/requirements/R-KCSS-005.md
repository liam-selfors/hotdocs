# R-KCSS-005

**R-KCSS-005** — `asset_runner(asset_file)` MUST return a callable
`run(entry: str, args: list)` that parses `asset_file` as it is at each
call and answers `"tokens"` and `"rule"` exactly as
`specs/architecture/asset-kind-css.md` "Running criteria" states. A
value is the declaration's text after its first `:`, comments removed,
stripped, each run of whitespace one space; a property is the text
before it, comments removed, stripped.
A rule's prelude is compared stripped, each run of whitespace one
space, so a prelude written `.a,\n.b` matches the selector `.a, .b`
and not `.a,.b`. `run` on a file whose layout is invalid, a
file that is not UTF-8 included, raises
`AssetError("invalid layout: <first layout_errors message>")`;
any other entry raises `AssetError("no entry <entry>")`.
