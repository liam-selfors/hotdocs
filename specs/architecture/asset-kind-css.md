---
id: arch-asset-kind-css
title: Asset kind css
status: draft
owners: [pipeline-team]
depends_on: []
---

# Asset kind `css`

A stylesheet a page inlines, read and checked in Python without a
browser (`D386`). `comp-kind-css` is its adapter.

## Layout

The asset is one UTF-8 file, usually `static/<name>.css`, holding a
sequence of rules. The scan reads it left to right: `/* ... */` is a
comment (to the end of the file when unclosed), skipped; a `'` or `"`
starts a string that ends at the next unescaped same quote, a backslash
escaping the next character; `{`, `}`, `;` and `:` outside strings and
comments are punctuation; everything else is text. A rule is a prelude
(the source from the end of the previous rule, declaration or block up
to `{`, its selectors) and a block of declarations, each
`<property>: <value>` ended by `;` or by the block's `}`. A prelude, a
property and a value are each that raw source slice with its comments
removed, so `:root` keeps its `:` and `color: /* x */ red` has the
value `red`. The one
at-rule allowed is `@media <condition> { <rules> }`, not nested.

`layout_errors` returns `["parse error: not UTF-8"]` alone for a file
that is not UTF-8. Otherwise it returns, in order: the first structural
error, if any, as `parse error: line <n>: <what>`, `<what>` one of
`unexpected }`, `unexpected {` (a block inside a rule's block),
`unexpected ;` (a `;` outside any block ending text that is not an
at-rule), `unclosed {`, `expected :` (a declaration with no `:`),
`at-rule @<name> is not allowed` (`@import "x.css";` included) and
`@media inside @media`; then one
`forbidden: url(`, `forbidden: expression(` or `forbidden: </style` per
occurrence, `url(` and `expression(` outside strings and comments,
`</style` anywhere, compared case-insensitively. `<n>` is 1 plus the
number of `\n` before the offending character. An empty list means the
layout is valid.

## Environment

None: the adapter reads the file in Python. `provision` always reports
exactly the four keys `ok` true, `reason` `""`, `versions` `{}` and
`lockfile_sha256` null, with no `interpreter` key, which only the
`python` kind reports.

## Surface

Every custom property (a property starting `--`) declared in a
top-level `:root` rule, and every class named in any rule's prelude,
written with its leading `.` (`.tone-ok` in `.node.tone-ok:hover`). The
interface file lists one name per line in a fenced block:

    --color-text
    .tone-ok

`surface(asset_file)["names"]` is the sorted list of those names, each
once.

## Running criteria

`asset_runner(path)` returns `run(entry, args)`, which parses the asset
as it is at call time, in the test's own process: the asset is never
executed, so no environment, process or timeout is involved, and the
parse is a single linear pass with no thread or signal. A value is its text stripped, with each run of whitespace
made one space.

- `run("tokens", [])`: a dict of every custom property declared in a
  top-level `:root` rule, name to value, a later declaration winning.
- `run("tokens", ["dark"])`: the same for `:root` inside `@media`
  whose condition, whitespace-collapsed, is
  `(prefers-color-scheme: dark)`.
- `run("rule", [selector])`: a dict of the declarations of every
  top-level rule whose prelude, whitespace-collapsed, equals
  `selector`, property to value, a later one winning;
  `AssetError("no rule <selector>")` when there is none.
- `run("contrast", [a, b])` and `run("contrast", [a, b, "dark"])`: the
  contrast ratio of the colour tokens `a` and `b`, from `tokens`, or for
  `"dark"` from the dark tokens with `tokens` filling any gap, computed
  as `specs/architecture/visual-style.md` "Contrast" states:
  each channel `v` of `#rrggbb` becomes `c = v / 255`, then
  `c / 12.92` when `c <= 0.04045`, else `((c + 0.055) / 1.055) ** 2.4`;
  luminance `0.2126 * R + 0.7152 * G + 0.0722 * B`; ratio
  `(lighter + 0.05) / (darker + 0.05)`, rounded to two decimals.
  `AssetError("no token <name>")` for a missing token,
  `AssetError("not a #rrggbb colour: <name>")` for another value.

Any other entry raises `AssetError("no entry <entry>")`.

    run = asset_runner("static/style.css")
    run("rule", [".tone-ok"])   # -> {"border-left": "4px solid var(--color-ok)"}

## Strength check

Mutation. Every declaration, in any rule, `@media` included, is one
site, in text order: the mutant deletes it, from the first character of
its property through its `;` (or to just before the block's `}` when it
has none). Each site's `description` is `<line>: <property> removed`,
`<line>` the property's line.

## Test author guidance

Call the asset only through the `asset_runner` fixture:
`run = asset_runner("<declared path>")`, then `run("rule", [selector])`,
`run("tokens", [])`, `run("tokens", ["dark"])` or
`run("contrast", [a, b])`, and compare the result with exact expected
values. Never parse the `.css` file's text yourself or search it for
words: a test that passes because a word is present checks nothing.
Reading the file is allowed only to compare its whole text with
something that must contain it verbatim, such as a page that inlines
it, or to check that a text the layout forbids is absent. Catch failures as `pytest.raises(Exception, match=...)` on the
message; the exception type is the adapter's.

## Generator guidance

Write plain CSS: rules of selectors and declarations, `:root` custom
properties for every value a token names, and `@media` only one level
deep. No `@import`, `@font-face` or other at-rule, no `url(`, no
`expression(`, no `!important`, and no vendor hacks (a vendor-prefixed
font-family keyword such as `-apple-system` is a plain value, not a
hack). Write every
colour as `#rrggbb` in lowercase. The text `</style` appears nowhere in
the file, so a page can inline it.
