# R-KPY-002

**R-KPY-002** — `layout_errors(asset_file)` MUST parse each Python file
of the code directory (`interface/library.md`), in order, with
`ast.parse(<the file's bytes>)` and no other argument, so the source's
own encoding rules apply. The parse runs in the module's own
process, under the Python running it (`hotdocs`'), never a subprocess.
For each file whose parse raises `SyntaxError` or `ValueError`, it adds
the message

    <relative path>:<line>: SyntaxError: <msg>

`<line>` the exception's `lineno`, or `0` when it has none or `None`,
and `<msg>` its `msg` (a `ValueError`'s `str`). The result is the list of these messages, `[]` when
every file parses. Files that are not Python files (another suffix, or
under `__pycache__`) are never read. It never raises for a file that
does not parse.
