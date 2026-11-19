# R-KPY-004

**R-KPY-004** — `provision(repo_root)` MUST return a `ProvisionResult`
and never raise (`D345`). First, when
`<repo_root>/environments/python/python-version` is a file whose
stripped text `pin` is non-empty, `platform.python_version()` of the
running interpreter must equal `pin` or start with `pin + "."` (`3.1`
does not match `3.14.6`); else it returns, before anything is created,
`ok` false with `reason`
`python environment: needs Python <pin>, found <version>`.

When `<repo_root>/environments/python/requirements.lock` is not a file,
it writes nothing and its `interpreter` is `sys.executable`,
`lockfile_sha256` `None`; with a lock, `R-KPY-005` applies. Either way
`versions` is the JSON object printed by running
`[interpreter, "-I", "-c", <program>]` (30-second timeout), the program
exactly these four lines:

    import hashlib,json,platform,re
    from importlib.metadata import distributions as ds
    s=sorted({re.sub(r'[-_.]+','-',str(d.metadata['Name']).lower())+'=='+str(d.version) for d in ds()})
    print(json.dumps({'python':platform.python_version(),'packages':'sha256:'+hashlib.sha256('\n'.join(s).encode()).hexdigest()}))

So a name repeated with one version counts once. When it exits
non-zero, times out or prints no JSON object, the result is `ok` false
with `reason` `python environment: python version check failed`.
Every failure has `versions` `{}` and `interpreter` `None`;
`lockfile_sha256` is the lock's whenever the lock exists.
