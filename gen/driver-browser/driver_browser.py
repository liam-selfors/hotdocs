"""Adapter for the `browser` test driver: a headless Chromium driven by
Playwright for Python, running in a helper process started from the
driver's own environment, exchanging one JSON object per line."""

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path, PurePath
from urllib.parse import urlsplit

NAME = "browser"
FIXTURE = "browser"
PLAYWRIGHT_VERSION = "1.64.1"

_ENV = Path(".hotdocs", "env", "driver-browser")
_HELPER = Path(__file__).with_name("driver_browser_helper.py")
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_TIMEOUT = 30

_GUIDANCE = """
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


class _StepFailed(Exception):
    pass


def _helper_env(home, env_dir):
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home),
        "PLAYWRIGHT_BROWSERS_PATH": str(env_dir / "browsers"),
    }


def _run(command, env=None):
    return subprocess.run(
        [str(part) for part in command], capture_output=True, text=True, env=env
    )


def _check(command, env=None):
    result = _run(command, env)
    if result.returncode != 0:
        lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
        raise _StepFailed(([""] + lines)[-1])
    return result


def _playwright_version(result):
    return result.stdout.strip().removeprefix("Version ")


def provision(repo_root):
    env_dir = Path(repo_root) / _ENV
    python = env_dir / "bin" / "python"
    try:
        if not python.exists():
            _check([sys.executable, "-m", "venv", env_dir])
        version_command = [python, "-m", "playwright", "--version"]
        playwright = _run(version_command)
        if playwright.returncode != 0 or _playwright_version(playwright) != PLAYWRIGHT_VERSION:
            _check([python, "-m", "pip", "install", f"playwright=={PLAYWRIGHT_VERSION}"])
            playwright = _check(version_command)
        chromium_command = [python, "-I", _HELPER, "--version"]
        helper_env = _helper_env(env_dir, env_dir)
        chromium = _run(chromium_command, helper_env)
        if chromium.returncode != 0:
            install_env = dict(os.environ)
            install_env["PLAYWRIGHT_BROWSERS_PATH"] = str(env_dir / "browsers")
            _check([python, "-m", "playwright", "install", "chromium"], install_env)
            chromium = _check(chromium_command, helper_env)
    except Exception as error:
        return {
            "ok": False,
            "reason": f"browser environment: {error}",
            "versions": {},
            "lockfile_sha256": None,
        }
    return {
        "ok": True,
        "reason": None,
        "versions": {
            "playwright": _playwright_version(playwright),
            "chromium": chromium.stdout.strip(),
        },
        "lockfile_sha256": None,
    }


def guidance():
    return {"test_author": _GUIDANCE.strip()}


def _pump(stream, replies):
    for line in iter(stream.readline, ""):
        replies.put(line)
    replies.put(json.dumps({"error": "browser process exited"}))


def _selector(css, role, name, label, text, test_id):
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
    described = f"{kind}={value}"
    if name is not None:
        described += f' name="{name}"'
    return {"kind": kind, "value": value, "name": name}, described


class Session:
    def __init__(self, repo_root, work_dir):
        self._env_dir = Path(repo_root) / _ENV
        self._work_dir = Path(work_dir).absolute()
        self._proc = None
        self._replies = None

    def _start(self):
        self._proc = subprocess.Popen(
            [str(self._env_dir / "bin" / "python"), "-I", str(_HELPER), str(self._work_dir)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=_helper_env(self._work_dir, self._env_dir),
            cwd=str(self._work_dir),
        )
        self._replies = queue.Queue()
        threading.Thread(
            target=_pump, args=(self._proc.stdout, self._replies), daemon=True
        ).start()

    def _call(self, op, **args):
        self._proc.stdin.write(json.dumps({"op": op, "args": args}) + "\n")
        self._proc.stdin.flush()
        try:
            line = self._replies.get(timeout=_TIMEOUT)
        except queue.Empty:
            proc, self._proc = self._proc, None
            proc.kill()
            proc.wait()
            raise BrowserError("timed out after 30 seconds")
        reply = json.loads(line)
        if "error" in reply:
            raise BrowserError(reply["error"])
        return reply["value"]

    def _target(self, target):
        if isinstance(target, str) and urlsplit(target).scheme:
            parts = urlsplit(target)
            if parts.scheme == "http" and parts.hostname in _LOOPBACK:
                return target, None
            raise BrowserError(f"only file paths and loopback URLs can be opened: {target}")
        if not isinstance(target, (str, PurePath)):
            raise BrowserError(f"only file paths and loopback URLs can be opened: {target}")
        path = self._work_dir / target
        if not path.is_file():
            raise BrowserError(f"no such file: {path}")
        resolved = path.resolve()
        return resolved.as_uri(), str(resolved.parent)

    def open(self, target, *, width=1280, height=800, color_scheme="light"):
        if color_scheme not in ("light", "dark"):
            raise BrowserError(f"color_scheme is light or dark: {color_scheme}")
        url, allowed_dir = self._target(target)
        if self._proc is None:
            self._start()
        page_id = self._call(
            "open",
            url=url,
            allowed_dir=allowed_dir,
            width=width,
            height=height,
            color_scheme=color_scheme,
        )
        return Page(self, page_id)

    def close(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        proc.stdin.close()
        try:
            proc.wait(timeout=_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


class Page:
    def __init__(self, session, page_id):
        self._session = session
        self._id = page_id

    def _call(self, op, **args):
        return self._session._call(op, page=self._id, **args)

    def find(self, css=None, *, role=None, name=None, label=None, text=None, test_id=None):
        step, described = _selector(css, role, name, label, text, test_id)
        return Element(self, [step], described)

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
        return [Path(path) for path in self._call("downloads")]

    def screenshot(self, name):
        return Path(self._call("screenshot", name=name))


class Element:
    def __init__(self, page, steps, selector):
        self._page = page
        self._steps = steps
        self._selector = selector

    def _do(self, method, *args):
        return self._page._call(
            "element",
            steps=self._steps,
            selector=self._selector,
            method=method,
            args=list(args),
        )

    def click(self, *, modifiers=()):
        self._do("click", list(modifiers))

    def dblclick(self):
        self._do("dblclick")

    def hover(self):
        self._do("hover")

    def fill(self, text):
        self._do("fill", text)

    def press(self, key):
        self._do("press", key)

    def select(self, value):
        self._do("select", value)

    def check(self):
        self._do("check")

    def uncheck(self):
        self._do("uncheck")

    def wheel(self, dx, dy):
        self._do("wheel", dx, dy)

    def drag_by(self, dx, dy):
        self._do("drag_by", dx, dy)

    def text(self):
        return self._do("text")

    def value(self):
        return self._do("value")

    def attribute(self, name):
        return self._do("attribute", name)

    def checked(self):
        return self._do("checked")

    def box(self):
        return self._do("box")

    def style(self, property):
        return self._do("style", property)

    def count(self):
        return self._do("count")

    def texts(self):
        return self._do("texts")

    def visible(self):
        return self._do("visible")

    def nth(self, i):
        return Element(self._page, self._steps + [{"nth": i}], f"{self._selector} >> nth={i}")

    def find(self, css=None, *, role=None, name=None, label=None, text=None, test_id=None):
        step, described = _selector(css, role, name, label, text, test_id)
        return Element(self._page, self._steps + [step], f"{self._selector} >> {described}")


def open_session(repo_root, work_dir):
    return Session(repo_root, work_dir)
