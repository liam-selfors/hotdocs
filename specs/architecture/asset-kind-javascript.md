---
id: arch-asset-kind-javascript
title: Asset kind javascript
status: draft
owners: [pipeline-team]
depends_on: []
---

# Asset kind `javascript`

An ES module whose logic is pure functions over JSON values, run in Node
for criteria and in a browser by whatever page includes it (`D343`).
`comp-kind-javascript` is its adapter.

## Layout

The asset is one UTF-8 file, usually `static/<name>.js`. It MUST parse
as an ES module (`node --check` on a copy named `<name>.mjs` exits 0)
and MUST NOT use, outside strings and comments, the name `import`,
`require(`, `fetch(`, `XMLHttpRequest` or `WebSocket`. `layout_errors`
returns, in order: `parse error: not UTF-8` alone for a file that is not
UTF-8; else `parse error: <line>`, `<line>` the first line of Node's
stderr starting `SyntaxError:` (else its first non-empty line), or
`parse error: timed out after 30 seconds`; then one
`forbidden: import`, `forbidden: require(`, `forbidden: fetch(`,
`forbidden: XMLHttpRequest` or `forbidden: WebSocket` per occurrence.
An empty list means the layout is valid. A missing Node is the
environment's failure, reported by `provision` before layout is checked.

## Environment

Node, minimum version 24, version from `node --version` (`v24.1.0`
reports `24.1.0`). No packages and no lockfile: `lockfile_sha256` is
null. `provision` reports `javascript needs node >= 24` when `node` is
not on `PATH` or is older.

## Surface

The asset's exported names. The interface file lists one export per
line in a fenced block, as a signature:

    export function filterNodes(nodes, query)
    export function init(document)

`surface(asset_file)["names"]` is the sorted list of the module's
export names, read by importing a copy of it in Node.

## Running criteria

`asset_runner(path)` returns `run(entry, args)`. `run` imports a fresh
copy of the asset as an ES module in a new `node` process, calls the
export `entry` with `args` spread as its arguments, awaits the result if
it is a promise, and returns it as decoded JSON, `None` for `undefined`.
When the export throws, `run` raises `AssetError` with the thrown
error's `message`; when `entry` is not an exported function, `AssetError`
with `no export <entry>`. Arguments and results are JSON only: a
function, a DOM node or `undefined` inside a value cannot cross. The
process gets no environment variables beyond `PATH` and may read only
the copy and the adapter's driver script (`node --permission --allow-fs-read=<copy> --allow-fs-read=<driver>`).

    run = asset_runner("static/app.js")
    run("filterNodes", [[{"id": "a", "label": "Gen"}], "gen"])  # -> ["a"]

## Strength check

Mutation. Every token of the file is read left to right, skipping
`'...'`, `"..."` and `` `...` `` strings (a backslash escapes the next
character; a template's `${...}` is skipped with it) and `//` and
`/* */` comments. Each of these tokens is a site, swapped `===`↔`!==`,
`==`↔`!=`, `<`↔`>=`, `>`↔`<=`, `<=`↔`>`, `>=`↔`<`, `&&`↔`||`,
`true`↔`false`, and `+`↔`-` when the token before it is a number, `)`,
`]`, or a name other than `return`, `typeof`, `void`, `delete`, `throw`,
`new`, `in`, `of`, `instanceof`, `case`, `do`, `else`, `yield` or
`await` (so `return -x` has no site). Longer operators are read first, so `===`, `=>`,
`++`, `+=`, `<<`, `>>` and `>>>` are never split or mutated. Sites are
listed in text order; each site's `description` is
`<line>: <token> -> <swap>`, and `apply_site` rewrites the file with that
one token replaced.

## Test author guidance

Call the asset only through the `asset_runner` fixture:
`run = asset_runner("<declared path>")`, then `run("<export>", [args])`,
and compare the returned JSON with exact expected values. Every argument
is plain JSON (dicts, lists, strings, numbers, booleans, `None`). Never
start `node` yourself or search the `.js` file's text for words: a test
that passes because a word is present checks nothing. Reading the file
is allowed only to compare its whole text with something that must
contain it verbatim, such as a page that inlines it. An
export that takes a DOM object, such as `init(document)`, is not called
by tests. Catch failures as `pytest.raises(Exception, match=...)` on the
thrown message; the exception type is the adapter's.

## Generator guidance

Write the asset as an ES module of pure functions over JSON values,
each exported with `export function <name>(...)`, plus at most one
export `init(document)` that only wires browser events to those
functions: `init` contains no comparison, logical or arithmetic
operator, no `true` or `false` and no condition, so every decision, and
every mutation site, is in a pure export that tests call. No imports, no network, no `eval`, no globals beyond the
module's own, and no regular expression literals (write
`new RegExp("...")`), which the strength check's scan does not read.
The text `</script` appears nowhere in the file, so a page can inline it.
A page using the asset inlines its text in
`<script type="module">` followed by `init(document);`.
