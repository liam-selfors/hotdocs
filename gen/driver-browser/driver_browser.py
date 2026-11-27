"""Browser test driver adapter: headless Chromium through Playwright for Python.

The test's own process never imports Playwright. This same file, run with
the environment's interpreter, is the helper process that drives the
browser, exchanging one JSON object per line on its standard input and
output.
"""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

NAME = "browser"
FIXTURE = "browser"
PLAYWRIGHT_VERSION = "1.64.1"

_TIMEOUT = 30
_LOOPBACK = ("127.0.0.1", "localhost", "::1")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

_GUIDANCE = """Drive pages only through the `browser` fixture. Build the page with
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
`count`, `visible`, `value`, `attribute`, `url`) and on
`console_errors()`, never on pixels or on `screenshot` files. Every
selector and expected text comes from the criterion, the requirement
or the interface; a criterion that needs one they do not state is a
spec gap, not something to guess. Do not import Playwright, start a
browser, or open any URL beyond a file in `tmp_path` or a loopback
server the test started. Catch failures as
`pytest.raises(Exception, match=...)` on the message."""


class BrowserError(Exception):
    """Raised by every session, page and element method."""


def _env_dir(repo_root):
    return Path(repo_root) / ".hotdocs" / "env" / "driver-browser"


# ---------------------------------------------------------------- provision


def _last_line(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _fail(reason):
    return {
        "ok": False,
        "reason": f"browser environment: {reason}",
        "versions": {},
        "lockfile_sha256": None,
    }


def _run(cmd, env=None):
    return subprocess.run(
        [str(c) for c in cmd], capture_output=True, text=True, env=env
    )


def _playwright_version(result):
    return result.stdout.strip().removeprefix("Version ")


def _provision(repo_root):
    env = _env_dir(repo_root)
    python = env / "bin" / "python"
    penv = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(env / "browsers"))
    if not python.exists():
        made = _run([sys.executable, "-m", "venv", env])
        if made.returncode:
            return _fail(_last_line(made.stderr))
    pw = _run([python, "-m", "playwright", "--version"])
    if pw.returncode or _playwright_version(pw) != PLAYWRIGHT_VERSION:
        installed = _run(
            [python, "-m", "pip", "install", f"playwright=={PLAYWRIGHT_VERSION}"]
        )
        if installed.returncode:
            return _fail(_last_line(installed.stderr))
        pw = _run([python, "-m", "playwright", "--version"])
        if pw.returncode:
            return _fail(_last_line(pw.stderr))
    helper = Path(__file__).resolve()
    chromium = _run([python, helper, "--version"], env=penv)
    if chromium.returncode:
        installed = _run([python, "-m", "playwright", "install", "chromium"], env=penv)
        if installed.returncode:
            return _fail(_last_line(installed.stderr))
        chromium = _run([python, helper, "--version"], env=penv)
        if chromium.returncode:
            return _fail(_last_line(chromium.stderr))
    return {
        "ok": True,
        "reason": None,
        "versions": {
            "playwright": _playwright_version(pw),
            "chromium": chromium.stdout.strip(),
        },
        "lockfile_sha256": None,
    }


def provision(repo_root):
    try:
        return _provision(Path(repo_root))
    except Exception as exc:  # provision never raises
        return _fail(_last_line(str(exc)))


def guidance():
    return {"test_author": _GUIDANCE.strip()}


# ---------------------------------------------------------------- session


def _pump(stream, lines):
    for line in iter(stream.readline, ""):
        lines.put(line)
    lines.put(None)


def _selector_step(css, role, name, label, text, test_id):
    given = [
        (kind, value)
        for kind, value in (
            ("css", css),
            ("role", role),
            ("label", label),
            ("text", text),
            ("test_id", test_id),
        )
        if value is not None
    ]
    if len(given) != 1 or (name is not None and role is None):
        raise BrowserError("find takes exactly one selector")
    kind, value = given[0]
    return {"kind": kind, "value": value, "name": name}


def _describe(steps):
    parts = []
    for step in steps:
        if "nth" in step:
            parts.append(f"nth={step['nth']}")
        else:
            part = f"{step['kind']}={step['value']}"
            if step["name"] is not None:
                part += f' name="{step["name"]}"'
            parts.append(part)
    return " >> ".join(parts)


class Session:
    def __init__(self, repo_root, work_dir):
        self._repo_root = Path(repo_root)
        self._work_dir = Path(work_dir)
        self._proc = None
        self._lines = None

    def _start(self):
        env = _env_dir(self._repo_root)
        self._proc = subprocess.Popen(
            [
                str(env / "bin" / "python"),
                str(Path(__file__).resolve()),
                "--serve",
                str(self._work_dir),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(self._work_dir),
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": str(self._work_dir),
                "PLAYWRIGHT_BROWSERS_PATH": str(env / "browsers"),
            },
            text=True,
            bufsize=1,
        )
        self._lines = queue.Queue()
        threading.Thread(
            target=_pump, args=(self._proc.stdout, self._lines), daemon=True
        ).start()

    def _kill(self):
        proc = self._proc
        self._proc = None
        proc.kill()
        proc.wait()

    def _call(self, request):
        if self._proc is None:
            self._start()
        self._proc.stdin.write(json.dumps(request) + "\n")
        self._proc.stdin.flush()
        try:
            line = self._lines.get(timeout=_TIMEOUT)
        except queue.Empty:
            self._kill()
            raise BrowserError("timed out after 30 seconds") from None
        response = json.loads(line)
        if not response["ok"]:
            raise BrowserError(response["error"])
        return response["value"]

    def open(self, target, *, width=1280, height=800):
        directory = None
        if isinstance(target, str) and _SCHEME.match(target):
            parts = urlsplit(target)
            if parts.scheme != "http" or parts.hostname not in _LOOPBACK:
                raise BrowserError(
                    f"only file paths and loopback URLs can be opened: {target}"
                )
            url = target
        elif isinstance(target, (str, Path)):
            path = Path(target)
            if not path.is_absolute():
                path = self._work_dir / path
            if not path.is_file():
                raise BrowserError(f"no such file: {path}")
            url = path.as_uri()
            directory = path.parent.as_uri()
        else:
            raise BrowserError(
                f"only file paths and loopback URLs can be opened: {target}"
            )
        page_id = self._call(
            {"op": "open", "url": url, "dir": directory, "width": width, "height": height}
        )
        return Page(self, page_id)

    def close(self):
        proc = self._proc
        if proc is None:
            return
        self._proc = None
        try:
            proc.stdin.write(json.dumps({"op": "close"}) + "\n")
            proc.stdin.close()
            proc.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
            proc.wait()


class Page:
    def __init__(self, session, page_id):
        self._session = session
        self._id = page_id

    def _page(self, method, **args):
        return self._session._call(
            {"op": "page", "page": self._id, "method": method, "args": args}
        )

    def find(self, css=None, *, role=None, name=None, label=None, text=None, test_id=None):
        step = _selector_step(css, role, name, label, text, test_id)
        return Element(self._session, self._id, [step])

    def press(self, key):
        self._page("press", key=key)

    def set_size(self, width, height):
        self._page("set_size", width=width, height=height)

    def url(self):
        return self._page("url")

    def title(self):
        return self._page("title")

    def console_errors(self):
        return self._page("console_errors")

    def blocked_requests(self):
        return self._page("blocked_requests")

    def dialogs(self):
        return self._page("dialogs")

    def downloads(self):
        return [Path(p) for p in self._page("downloads")]

    def screenshot(self, name):
        return Path(self._page("screenshot", name=name))


class Element:
    def __init__(self, session, page_id, steps):
        self._session = session
        self._page_id = page_id
        self._steps = steps

    def _op(self, method, **args):
        return self._session._call(
            {
                "op": "element",
                "page": self._page_id,
                "steps": self._steps,
                "desc": _describe(self._steps),
                "method": method,
                "args": args,
            }
        )

    def click(self, *, modifiers=()):
        self._op("click", modifiers=list(modifiers))

    def dblclick(self):
        self._op("dblclick")

    def hover(self):
        self._op("hover")

    def fill(self, text):
        self._op("fill", text=text)

    def press(self, key):
        self._op("press", key=key)

    def select(self, value):
        self._op("select", value=value)

    def check(self):
        self._op("check")

    def uncheck(self):
        self._op("uncheck")

    def wheel(self, dx, dy):
        self._op("wheel", dx=dx, dy=dy)

    def drag_by(self, dx, dy):
        self._op("drag_by", dx=dx, dy=dy)

    def text(self):
        return self._op("text")

    def value(self):
        return self._op("value")

    def attribute(self, name):
        return self._op("attribute", name=name)

    def checked(self):
        return self._op("checked")

    def box(self):
        return self._op("box")

    def count(self):
        return self._op("count")

    def texts(self):
        return self._op("texts")

    def visible(self):
        return self._op("visible")

    def nth(self, i):
        return Element(self._session, self._page_id, self._steps + [{"nth": i}])

    def find(self, css=None, *, role=None, name=None, label=None, text=None, test_id=None):
        step = _selector_step(css, role, name, label, text, test_id)
        return Element(self._session, self._page_id, self._steps + [step])


def open_session(repo_root, work_dir):
    return Session(repo_root, work_dir)


# ---------------------------------------------------------------- helper process

_FRAMES = (
    "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r())))"
)
_ACTIONS = {
    "click", "dblclick", "hover", "fill", "press", "select",
    "check", "uncheck", "wheel", "drag_by",
}
_ONE_READS = {"text", "value", "attribute", "checked", "box"}


class _HelperError(Exception):
    pass


def _norm(text):
    return " ".join(text.split())


def _allowed(url, directory):
    if url.startswith(("data:", "blob:")):
        return True
    if directory is not None and url.startswith(directory + "/"):
        return True
    parts = urlsplit(url)
    return parts.scheme == "http" and parts.hostname in _LOOPBACK


class _Helper:
    def __init__(self, browser, work_dir):
        self.work_dir = work_dir
        self.context = browser.new_context(
            locale="en-US",
            timezone_id="UTC",
            device_scale_factor=1,
            reduced_motion="reduce",
            color_scheme="light",
            service_workers="block",
            accept_downloads=True,
        )
        self.context.set_default_timeout(5000)
        self.pages = []

    def handle(self, request):
        if request["op"] == "open":
            return self.open(request)
        state = self.pages[request["page"]]
        if request["op"] == "page":
            return self.page_op(state, request["method"], request["args"])
        return self.element_op(state, request)

    def open(self, request):
        page = self.context.new_page()
        state = {
            "page": page, "errors": [], "blocked": [], "dialogs": [],
            "pending": [], "saved": [],
        }
        directory = request["dir"]

        def on_console(message):
            if message.type == "error":
                state["errors"].append(message.text)

        def on_pageerror(error):
            state["errors"].append(f"{error.name}: {error.message}")

        def on_dialog(dialog):
            state["dialogs"].append(dialog.message)
            dialog.accept()

        def on_download(download):
            state["pending"].append(download)

        def on_route(route):
            url = route.request.url
            if _allowed(url, directory):
                route.continue_()
            else:
                state["blocked"].append(url)
                route.abort()

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("dialog", on_dialog)
        page.on("download", on_download)
        page.route("**/*", on_route)
        page.set_viewport_size({"width": request["width"], "height": request["height"]})
        page.goto(request["url"], wait_until="load", timeout=0)
        page.evaluate(_FRAMES)
        self.pages.append(state)
        return len(self.pages) - 1

    def page_op(self, state, method, args):
        page = state["page"]
        if method == "press":
            page.keyboard.press(args["key"])
            page.evaluate(_FRAMES)
            return None
        if method == "set_size":
            page.set_viewport_size({"width": args["width"], "height": args["height"]})
            page.evaluate(_FRAMES)
            return None
        if method == "url":
            return page.url
        if method == "title":
            return page.title()
        if method == "console_errors":
            return list(state["errors"])
        if method == "blocked_requests":
            return list(state["blocked"])
        if method == "dialogs":
            return list(state["dialogs"])
        if method == "downloads":
            folder = self.work_dir / "downloads"
            for download in state["pending"]:
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / download.suggested_filename
                download.save_as(target)
                state["saved"].append(str(target))
            state["pending"].clear()
            return list(state["saved"])
        folder = self.work_dir / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{args['name']}.png"
        page.screenshot(path=str(target), full_page=True)
        return str(target)

    @staticmethod
    def locate(page, steps):
        locator = page
        for step in steps:
            if "nth" in step:
                locator = locator.nth(step["nth"])
                continue
            kind, value = step["kind"], step["value"]
            if kind == "css":
                locator = locator.locator(value)
            elif kind == "role":
                if step["name"] is None:
                    locator = locator.get_by_role(value)
                else:
                    locator = locator.get_by_role(value, name=step["name"], exact=True)
            elif kind == "label":
                locator = locator.get_by_label(value, exact=True)
            elif kind == "text":
                locator = locator.get_by_text(value, exact=True)
            else:
                locator = locator.get_by_test_id(value)
        return locator

    @staticmethod
    def resolve(page, locator, desc, enabled):
        deadline = time.monotonic() + 5
        while True:
            n = locator.count()
            if n == 1 and locator.is_visible() and (not enabled or locator.is_enabled()):
                return
            if time.monotonic() >= deadline:
                break
            page.wait_for_timeout(50)
        if n > 1:
            raise _HelperError(f"{n} elements match {desc}")
        raise _HelperError(f"no element matches {desc}")

    def element_op(self, state, request):
        page = state["page"]
        locator = self.locate(page, request["steps"])
        method, args = request["method"], request["args"]
        if method in _ACTIONS:
            self.resolve(page, locator, request["desc"], True)
            self.act(page, locator, method, args)
            page.evaluate(_FRAMES)
            return None
        if method in _ONE_READS:
            self.resolve(page, locator, request["desc"], False)
            if method == "text":
                return _norm(locator.inner_text())
            if method == "value":
                return locator.input_value()
            if method == "attribute":
                return locator.get_attribute(args["name"])
            if method == "checked":
                return locator.is_checked()
            box = locator.bounding_box()
            return {k: round(box[k]) for k in ("x", "y", "width", "height")}
        if method == "count":
            return locator.count()
        if method == "texts":
            return [_norm(t) for t in locator.all_inner_texts()]
        return any(locator.nth(i).is_visible() for i in range(locator.count()))

    @staticmethod
    def act(page, locator, method, args):
        if method == "click":
            locator.click(modifiers=args["modifiers"])
        elif method == "dblclick":
            locator.dblclick()
        elif method == "hover":
            locator.hover()
        elif method == "fill":
            locator.fill(args["text"])
        elif method == "press":
            locator.press(args["key"])
        elif method == "select":
            locator.select_option(value=args["value"])
        elif method == "check":
            locator.check()
        elif method == "uncheck":
            locator.uncheck()
        else:
            box = locator.bounding_box()
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            page.mouse.move(x, y)
            if method == "wheel":
                page.mouse.wheel(args["dx"], args["dy"])
            else:
                page.mouse.down()
                page.mouse.move(x + args["dx"], y + args["dy"], steps=10)
                page.mouse.up()


def _serve(browser, work_dir):
    helper = _Helper(browser, work_dir)
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        request = json.loads(line)
        if request["op"] == "close":
            break
        try:
            response = {"ok": True, "value": helper.handle(request)}
        except Exception as exc:
            response = {"ok": False, "error": str(exc).split("\n", 1)[0]}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def _helper_main(argv):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        if argv[0] == "--version":
            print(browser.version)
        else:
            _serve(browser, Path(argv[1]))
        browser.close()


if __name__ == "__main__":
    _helper_main(sys.argv[1:])
