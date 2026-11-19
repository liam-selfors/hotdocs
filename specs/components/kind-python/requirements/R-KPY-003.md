# R-KPY-003

**R-KPY-003** — `surface(asset_file)` MUST return `{"names": names}`,
`names` the sorted list of the module's `dir()` entries that do not
start with `_`. It runs the interpreter as `interface/library.md` "The
interpreter" states, with the arguments `-c`, the program below
(exactly, two lines) and the module name:

    import importlib,json,sys
    print('\n'+json.dumps(sorted(n for n in dir(importlib.import_module(sys.argv[1])) if not n.startswith('_'))))

When the process exits non-zero, times out, or prints no last line
that decodes to a list, `names` is `[]`; `surface` never raises.
