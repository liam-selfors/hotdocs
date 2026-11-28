"""Adapter for the `browser` test driver: a headless Chromium driven
through Playwright for Python, run in a helper process of its own."""

import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path, PurePath
from urllib.parse import urlsplit

NAME = "browser"
FIXTURE = "browser"
PLAYWRIGHT_VERSION = "1.64.1"

_HELPER = Path(__file__).resolve().parent / "_driver_browser_helper.py"
_TIMEOUT = 30
_TIMEOUT_MESSAGE = "timed out after 30 seconds"
_LOOPBACK = ("127.0.0.1", "localhost", "::1")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")

_GUIDANCE = """\
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
"""


class BrowserError(Exception):
    """Raised by every session, page and element method."""


def _env_dir(repo_root):
    return Path(repo_root) / ".hotdocs" / "env" / "driver-browser"


def _run(cmd, env):
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def _failed(reason):
    return {"ok": False, "reason": f"browser environment: {reason}",
            "versions": {}, "lockfile_sha256": None}


def _last_stderr_line(result):
    lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    return (lines or [""])[-1]


def provision(repo_root):
    env = _env_dir(repo_root)
    python = env / "bin" / "python"
    run_env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(env / "browsers"))
    try:
        if not python.exists():
            result = _run([sys.executable, "-m", "venv", str(env)], run_env)
            if result.returncode != 0:
                return _failed(_last_stderr_line(result))
        version_cmd = [str(python), "-m", "playwright", "--version"]
        result = _run(version_cmd, run_env)
        if result.stdout.strip() != f"Version {PLAYWRIGHT_VERSION}":
            result = _run([str(python), "-m", "pip", "install",
                           f"playwright=={PLAYWRIGHT_VERSION}"], run_env)
            if result.returncode != 0:
                return _failed(_last_stderr_line(result))
            result = _run(version_cmd, run_env)
        playwright_version = result.stdout.strip().removeprefix("Version ")
        chromium_cmd = [str(python), str(_HELPER), "--chromium-version"]
        result = _run(chromium_cmd, run_env)
        if result.returncode != 0:
            result = _run([str(python), "-m", "playwright", "install", "chromium"],
                          run_env)
            if result.returncode != 0:
                return _failed(_last_stderr_line(result))
            result = _run(chromium_cmd, run_env)
            if result.returncode != 0:
                return _failed(_last_stderr_line(result))
        chromium_version = result.stdout.strip()
    except Exception as exc:  # provision never raises
        return _failed(str(exc))
    return {"ok": True, "reason": None,
            "versions": {"playwright": playwright_version, "chromium": chromium_version},
            "lockfile_sha256": None}


def guidance():
    return {"test_author": _GUIDANCE.strip()}


def open_session(repo_root, work_dir):
    return Session(repo_root, work_dir)


def _find_step(css, role, name, label, text, test_id):
    given = [(kind, value) for kind, value in (
        ("css", css), ("role", role), ("label", label),
        ("text", text), ("test_id", test_id)) if value is not None]
    if len(given) != 1 or (name is not None and role is None):
        raise BrowserError("find takes exactly one selector")
    kind, value = given[0]
    selector = f"{kind}={value}"
    if name is not None:
        selector += f' name="{name}"'
    return {"kind": kind, "value": value, "name": name}, selector


class Session:
    def __init__(self, repo_root, work_dir):
        self._repo_root = Path(repo_root)
        self._work_dir = Path(work_dir).absolute()
        self._proc = None
        self._lines = None
        self._closed = False
        self._dead = False

    def _start(self):
        env = _env_dir(self._repo_root)
        self._proc = subprocess.Popen(
            [str(env / "bin" / "python"), str(_HELPER), str(self._work_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
            cwd=str(self._work_dir),
            env={"PATH": os.environ.get("PATH", os.defpath),
                 "HOME": str(self._work_dir),
                 "PLAYWRIGHT_BROWSERS_PATH": str(env / "browsers")})
        self._lines = queue.Queue()
        threading.Thread(target=self._read, args=(self._proc.stdout, self._lines),
                         daemon=True).start()

    @staticmethod
    def _read(stream, lines):
        for line in stream:
            lines.put(line)
        lines.put(None)

    def _call(self, op, **args):
        if self._dead:
            raise BrowserError(_TIMEOUT_MESSAGE)
        self._proc.stdin.write(json.dumps({"op": op, "args": args}) + "\n")
        self._proc.stdin.flush()
        try:
            line = self._lines.get(timeout=_TIMEOUT)
        except queue.Empty:
            self._dead = True
            self._closed = True
            self._proc.kill()
            self._proc.wait()
            raise BrowserError(_TIMEOUT_MESSAGE) from None
        if line is None:
            raise BrowserError("browser process exited")
        reply = json.loads(line)
        if not reply["ok"]:
            raise BrowserError(reply["error"])
        return reply["value"]

    def _resolve(self, target):
        if isinstance(target, str) and _SCHEME.match(target):
            parts = urlsplit(target)
            if parts.scheme == "http" and parts.hostname in _LOOPBACK:
                return target, None
            raise BrowserError(
                f"only file paths and loopback URLs can be opened: {target}")
        if not isinstance(target, (str, PurePath)):
            raise BrowserError(
                f"only file paths and loopback URLs can be opened: {target}")
        path = self._work_dir / Path(target)
        if not path.exists():
            raise BrowserError(f"no such file: {path}")
        return path.as_uri(), str(path.parent)

    def open(self, target, *, width=1280, height=800, color_scheme="light"):
        if color_scheme not in ("light", "dark"):
            raise BrowserError(f"color_scheme is light or dark: {color_scheme}")
        url, base_dir = self._resolve(target)
        if self._proc is None:
            self._start()
        page_id = self._call("open", url=url, base_dir=base_dir, width=width,
                             height=height, color_scheme=color_scheme)
        return Page(self, page_id)

    def close(self):
        if self._proc is None or self._closed:
            return
        self._closed = True
        self._call("close")
        self._proc.wait()


class Page:
    def __init__(self, session, page_id):
        self._session = session
        self._id = page_id

    def _call(self, op, **args):
        return self._session._call(op, page=self._id, **args)

    def find(self, css=None, *, role=None, name=None, label=None, text=None,
             test_id=None):
        step, selector = _find_step(css, role, name, label, text, test_id)
        return Element(self._session, self._id, [step], selector)

    def press(self, key):
        self._call("press", key=key)

    def set_size(self, width, height):
        self._call("set_size", width=width, height=height)

    def url(self):
        return self._call("url")

    def title(self):
        return self._call("title")

    def console_errors(self):
        return self._call("console_errors")

    def blocked_requests(self):
        return self._call("blocked_requests")

    def dialogs(self):
        return self._call("dialogs")

    def downloads(self):
        return [Path(p) for p in self._call("downloads")]

    def screenshot(self, name):
        return Path(self._call("screenshot", name=name))


class Element:
    def __init__(self, session, page_id, chain, selector):
        self._session = session
        self._page = page_id
        self._chain = chain
        self._selector = selector

    def _act(self, action, **args):
        self._session._call("act", page=self._page, chain=self._chain,
                            selector=self._selector, action=action, args=args)

    def _read(self, read, **args):
        return self._session._call("read", page=self._page, chain=self._chain,
                                   selector=self._selector, read=read, args=args)

    def _all(self, read):
        return self._session._call("all", page=self._page, chain=self._chain,
                                   read=read)

    # Actions
    def click(self, *, modifiers=()):
        self._act("click", modifiers=list(modifiers))

    def dblclick(self):
        self._act("dblclick")

    def hover(self):
        self._act("hover")

    def fill(self, text):
        self._act("fill", text=text)

    def press(self, key):
        self._act("press", key=key)

    def select(self, value):
        self._act("select", value=value)

    def check(self):
        self._act("check")

    def uncheck(self):
        self._act("uncheck")

    def wheel(self, dx, dy):
        self._act("wheel", dx=dx, dy=dy)

    def drag_by(self, dx, dy):
        self._act("drag_by", dx=dx, dy=dy)

    # Reads that need one element
    def text(self):
        return self._read("text")

    def value(self):
        return self._read("value")

    def attribute(self, name):
        return self._read("attribute", name=name)

    def checked(self):
        return self._read("checked")

    def box(self):
        return self._read("box")

    def style(self, property):
        return self._read("style", property=property)

    # Reads over every match
    def count(self):
        return self._all("count")

    def texts(self):
        return self._all("texts")

    def visible(self):
        return self._all("visible")

    def nth(self, i):
        return Element(self._session, self._page,
                       self._chain + [{"kind": "nth", "index": i}],
                       f"{self._selector} >> nth={i}")

    def find(self, css=None, *, role=None, name=None, label=None, text=None,
             test_id=None):
        step, selector = _find_step(css, role, name, label, text, test_id)
        return Element(self._session, self._page, self._chain + [step],
                       f"{self._selector} >> {selector}")
