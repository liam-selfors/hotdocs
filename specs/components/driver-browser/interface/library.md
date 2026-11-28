# Library

The importable module is `driver_browser`
(`gen/driver-browser/driver_browser.py`), the adapter
`specs/architecture/test-drivers.md` defines:

```
NAME: str            # "browser"
FIXTURE: str         # "browser"
PLAYWRIGHT_VERSION: str  # "1.64.1"
provision(repo_root: Path) -> dict
guidance() -> dict
open_session(repo_root: Path, work_dir: Path) -> Session
```

`BrowserError` is an `Exception` defined in this module. The session,
page and element objects, their methods and messages are
`specs/architecture/test-driver-browser.md`'s "Fixture"; `work_dir` is
the `tmp_path` that document names. The Playwright side runs in a
helper process the adapter starts with
`<repo_root>/.hotdocs/env/driver-browser/bin/python` and a driver script
of its own beside this module, exchanging one JSON object per line on
its standard input and output.

Every handler the helper gives Playwright (`page.on`, `page.route`) is
a function defined with `def` or `lambda`, never a bound built-in such
as `list.append`: Playwright sets an attribute on each handler, which a
built-in cannot hold.

Implements: `specs/architecture/test-drivers.md`, `specs/architecture/test-driver-browser.md`
