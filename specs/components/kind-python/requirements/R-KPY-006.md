# R-KPY-006

**R-KPY-006** — `asset_runner(asset_file)` MUST return a callable
`run(entry: str, args: list)`. Each call runs the interpreter as
`interface/library.md` "The interpreter" states, with the arguments
`-c`, the driver below (exactly these eight lines), the module name,
`entry` and `json.dumps(args)`:

    import importlib,json,sys
    m,e,a=sys.argv[1:4]
    try:
     f=getattr(importlib.import_module(m),e,None)
     o=json.dumps({'v':f(*json.loads(a))} if callable(f) else {'e':'no entry '+e})
    except BaseException as x:
     o=json.dumps({'e':str(x)})
    print('\n'+o)

So the code is imported as it is at call time. `run` decodes the last
line as a JSON object: with key `v` it returns that value; with key `e`
it raises `AssetError(<its value>)`: the exception's `str`, including a
result that is not JSON-serializable, or `no entry <entry>` when the
module has no callable of that name. A process still running after 30
seconds is killed and `run` raises
`AssetError("timed out after 30 seconds")`. When no line decodes to an
object, it raises
`AssetError("python exited <code>: <last non-empty stderr line>")`.
