---
id: arch-test-driver-browser
title: Test driver browser
status: draft
owners: [pipeline-team]
depends_on: [arch-test-drivers]
---

# Test driver `browser`

A headless Chromium, driven through Playwright for Python, that loads a
page a component wrote or serves and acts on it as a user would:
clicking, typing, pressing keys, scrolling and dragging, then reading
what the page shows (`D373`). `comp-driver-browser` is its adapter.

## Environment

Python 3.11 or later (the interpreter `hotdocs` runs on) and the
Playwright release the adapter pins as `PLAYWRIGHT_VERSION`, exactly
`"1.64.1"`, with the Chromium build that release installs. A newer pin
is a change to this document. `provision(repo_root)` builds,
on first use, a virtual environment at
`<repo_root>/.hotdocs/env/driver-browser/` holding exactly
`playwright==<PLAYWRIGHT_VERSION>`, then runs
`<env>/bin/python -m playwright install chromium` with
`PLAYWRIGHT_BROWSERS_PATH=<env>/browsers`. Both steps need network
access once; later calls only check them. `versions` is
`{"playwright": <python -m playwright --version, without its "Version " prefix>, "chromium": <the launched browser's version>}`.
No lockfile: `lockfile_sha256` is null, since one package is pinned.
A failed step reports `ok` false with
`browser environment: <the step's last non-empty stderr line>`.

## Fixture

The fixture is `browser`. It yields a session; each test gets its own
Chromium, started on the first `open` and closed at teardown. Every
method raises `BrowserError` (defined by the adapter) with the message
given, and every value crossing it is plain Python (`str`, `int`,
`bool`, `None`, `list`, `dict`, `Path`).

**Session**

- `open(target, *, width=1280, height=800, color_scheme="light") -> Page`
  — `color_scheme` is `"light"` or `"dark"`, the page's
  `prefers-color-scheme`, else `color_scheme is light or dark: <value>`;
  `target` is a
  file path (`str` or `Path`, absolute, or relative to the test's
  `tmp_path`) opened as a `file://` URL, or an `http://` URL whose host
  is `127.0.0.1`, `localhost` or `[::1]`. Anything else raises
  `only file paths and loopback URLs can be opened: <target>`; a missing
  file raises `no such file: <path>`, `<path>` its absolute path. Each
  `open` returns a new page; pages opened earlier stay open, each with
  its own reads, until `close()`. It returns once the page's `load`
  event has fired and two animation frames have passed.

**Page**

- `find(css=None, *, role=None, name=None, label=None, text=None, test_id=None) -> Element`
  — exactly one of `css`, `role`, `label`, `text`, `test_id`, else
  `find takes exactly one selector`; `name` only with `role`, matching
  the accessible name exactly. `text` matches an element's whole
  visible text, trimmed, exactly; `test_id` matches `data-testid`.
  An `Element` is a description, resolved each time it is used.
- `press(key)` — a key or chord as Playwright writes it (`"Escape"`,
  `"Control+K"`, `"/"`) to the focused element.
- `set_size(width, height)` — resizes the viewport, then two frames.
- `url() -> str`, `title() -> str`.
- `console_errors() -> list[str]` — in order, the text of every console
  message of type `error` and of every uncaught exception
  (`<name>: <message>`) since `open`.
- `blocked_requests() -> list[str]` — in order, the URL of every
  request refused under Isolation.
- `dialogs() -> list[str]` — in order, the message of every `alert`,
  `confirm` or `prompt`, each accepted with no input.
- `downloads() -> list[Path]` — in order, each file the page
  downloaded, saved under `<tmp_path>/downloads/` with its suggested
  name.
- `screenshot(name) -> Path` — a full-page PNG at
  `<tmp_path>/screenshots/<name>.png`. Its pixels are for people
  reading a failure; no criterion asserts on them (`D373`).

**Closing.** The session's `close()`, before it stops the browser, saves
a full-page PNG of each page still open, in the order they were opened,
as `<tmp_path>/screenshots/final-<n>.png`, `<n>` counting from `1`, so a
reviewer sees what every browser criterion left on screen (`D390`). A
page that cannot be captured is skipped, never an error; a second
`close()` saves nothing and does nothing.

**Element**

- Actions: `click(*, modifiers=())` (each of `"Shift"`, `"Alt"`,
  `"Control"`, `"Meta"`), `dblclick()`, `hover()`, `fill(text)`,
  `press(key)`, `select(value)` (a `<select>` option by value),
  `check()`, `uncheck()`, `wheel(dx, dy)` (the mouse over the element's
  centre, then a wheel event), `drag_by(dx, dy)` (press at the centre,
  move by `dx`, `dy` in 10 steps, release).
- Reads that need one element: `text() -> str` (visible text,
  trimmed), `value() -> str`, `attribute(name) -> str | None`,
  `checked() -> bool`, `box() -> dict` (`{"x", "y", "width",
  "height"}` in viewport pixels, rounded to integers),
  `style(property) -> str` (the computed value of `property`, as
  `getComputedStyle(element).getPropertyValue(property)` returns it,
  stripped: a colour as `rgb(r, g, b)` or `rgba(r, g, b, a)`, a length
  in `px`, a custom property's value as declared).
- Reads over every match, never waiting: `count() -> int`,
  `texts() -> list[str]`, `visible() -> bool` (at least one match is
  visible).
- `nth(i) -> Element` (0-based, among matches in document order) and
  `find(...) -> Element` (as `Page.find`, within this element's single
  match).

An action, and a read that needs one element, waits up to 5 seconds
for exactly one match that is visible (and enabled, for an action),
else raises `no element matches <selector>` or
`<n> elements match <selector>`, `<selector>` being the call as
written: `<kind>=<value>` with the value bare, then for a role with a
name ` name="<name>"` quoted, such as `css=li`, `label=Query` or
`role=button name="Add"`. An action returns after the
page's handlers for its events have run and two animation frames have
passed, so a read after it sees the result without waiting.

## Isolation

- The browser may load only `file://` URLs inside the opened file's
  directory, `data:` and `blob:` URLs, and `http://` URLs on a loopback
  host. Every other request is aborted and listed by
  `blocked_requests()`; a page that should work offline is shown to by
  an empty list.
- Each session is a fresh profile: no cookies, storage or cache from
  another test; locale `en-US`, time zone `UTC`, device scale factor 1,
  reduced motion, the colour scheme `open` was given (light unless
  asked), no service workers.
- Playwright runs in its own process, started by the adapter from the
  environment's interpreter, with an environment of only `PATH`,
  `HOME` (the test's `tmp_path`) and `PLAYWRIGHT_BROWSERS_PATH`. It may
  write only under `tmp_path`. The test's own process never imports
  Playwright.
- A single call that takes over 30 seconds ends the session and raises
  `timed out after 30 seconds`.

## Test author guidance

Drive pages only through the `browser` fixture. Build the page with
the component's own code, writing into `tmp_path`, then open it:

    write_site(model, tmp_path)            # the component's function
    page = browser.open(tmp_path / "index.html")
    page.find(role="tab", name="Dictionary").click()
    page.find(label="Filter columns").fill("email")
    assert page.find(css="#dictionary tbody tr").texts() == ["customers email string"]
    assert page.console_errors() == []

For a server, start it with the component's own function on port 0 in
a thread, open `http://127.0.0.1:<port>/`, and stop it in a `finally`.
Find elements the way a user would: by role and accessible name, label
or visible text; use `css` or `test_id` only for what the interface
names by id or class. Assert on what the page shows (`text`, `texts`,
`count`, `visible`, `value`, `attribute`, `url`, and `style` for a
look the criterion states) and on `console_errors()`, never on pixels
or on `screenshot` files. Every
selector and expected text comes from the criterion, the requirement
or the interface; a criterion that needs one they do not state is a
spec gap, not something to guess. Do not import Playwright, start a
browser, or open any URL beyond a file in `tmp_path` or a loopback
server the test started. Catch failures as
`pytest.raises(Exception, match=...)` on the message.
