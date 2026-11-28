"""Adapter for the `browser` test driver: a headless Chromium driven through
Playwright for Python, running in a helper process of its own."""

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

NAME = "browser"
FIXTURE = "browser"
PLAYWRIGHT_VERSION = "1.64.1"

_TIMEOUT = 30
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_HELPER = Path(__file__).with_name("driver_browser_helper.py")

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
`count`, `visible`, `value`, `attribute`, `url`, and `style` for a
look the criterion states) and on `console_errors()`, never on pixels
or on `screenshot` files. Every
selector and expected text comes from the criterion, the requirement
or the interface; a criterion that needs one they do not state is a
spec gap, not something to guess. Do not import Playwright, start a
browser, or open any URL beyond a file in `tmp_path` or a loopback
server the test started. Catch failures as
`pytest.raises(Exception, match=...)` on the message."""


class BrowserError(Exception):
    pass


def _env_dir(repo_root):
    return Path(repo_root) / ".hotdocs" / "env" / "driver-browser"


def guidance():
    return {"test_author": _GUIDANCE.strip()}


# ---------------------------------------------------------------- provision

class _StepFailed(Exception):
    pass


def _last_line(text):
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _run(cmd, env):
    return subprocess.run(
        [str(c) for c in cmd], capture_output=True, text=True, env=env
    )


def _step(cmd, env):
    proc = _run(cmd, env)
    if proc.returncode != 0:
        raise _StepFailed(_last_line(proc.stderr))
    return proc.stdout


def _playwright_version(python, env):
    proc = _run([python, "-m", "playwright", "--version"], env)
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if out.startswith("Version "):
        out = out[len("Version "):]
    return out.strip()


def _chromium_version(python, env):
    return _run([python, str(_HELPER), "--chromium-version"], env)


def provision(repo_root):
    try:
        env_dir = _env_dir(repo_root)
        python = env_dir / "bin" / "python"
        env = dict(os.environ)
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(env_dir / "browsers")
        if not python.exists():
            _step([sys.executable, "-m", "venv", env_dir], env)
        pw_version = _playwright_version(python, env)
        if pw_version != PLAYWRIGHT_VERSION:
            _step([python, "-m", "pip", "install",
                   "playwright==" + PLAYWRIGHT_VERSION], env)
            pw_version = _playwright_version(python, env)
        chrom = _chromium_version(python, env)
        if chrom.returncode != 0:
            _step([python, "-m", "playwright", "install", "chromium"], env)
            chrom = _chromium_version(python, env)
            if chrom.returncode != 0:
                raise _StepFailed(_last_line(chrom.stderr))
        return {
            "ok": True,
            "reason": None,
            "versions": {"playwright": pw_version,
                         "chromium": chrom.stdout.strip()},
            "lockfile_sha256": None,
        }
    except Exception as exc:  # provision never raises
        return {
            "ok": False,
            "reason": "browser environment: " + str(exc),
            "versions": {},
            "lockfile_sha256": None,
        }


# ------------------------------------------------------------------ session

def _describe(kind, value, name):
    desc = f"{kind}={value}"
    if kind == "role" and name is not None:
        desc += f' name="{name}"'
    return desc


def _selector_step(css, role, name, label, text, test_id):
    given = [(k, v) for k, v in (("css", css), ("role", role),
                                 ("label", label), ("text", text),
                                 ("test_id", test_id)) if v is not None]
    if len(given) != 1:
        raise BrowserError("find takes exactly one selector")
    kind, value = given[0]
    step = {"kind": kind, "value": value}
    if kind == "role":
        step["name"] = name
    return step, _describe(kind, value, name if kind == "role" else None)


class Element:
    def __init__(self, page, steps, desc):
        self._page = page
        self._steps = steps
        self._desc = desc

    def _call(self, method, *params):
        return self._page._session._call(
            "element", page=self._page._id, steps=self._steps,
            desc=self._desc, method=method, params=list(params))

    # actions
    def click(self, *, modifiers=()):
        return self._call("click", list(modifiers))

    def dblclick(self):
        return self._call("dblclick")

    def hover(self):
        return self._call("hover")

    def fill(self, text):
        return self._call("fill", text)

    def press(self, key):
        return self._call("press", key)

    def select(self, value):
        return self._call("select", value)

    def check(self):
        return self._call("check")

    def uncheck(self):
        return self._call("uncheck")

    def wheel(self, dx, dy):
        return self._call("wheel", dx, dy)

    def drag_by(self, dx, dy):
        return self._call("drag_by", dx, dy)

    # reads needing one element
    def text(self):
        return self._call("text")

    def value(self):
        return self._call("value")

    def attribute(self, name):
        return self._call("attribute", name)

    def checked(self):
        return self._call("checked")

    def box(self):
        return self._call("box")

    def style(self, property):
        return self._call("style", property)

    # reads over every match
    def count(self):
        return self._call("count")

    def texts(self):
        return self._call("texts")

    def visible(self):
        return self._call("visible")

    def nth(self, i):
        return Element(self._page, self._steps + [{"nth": i}], self._desc)

    def find(self, css=None, *, role=None, name=None, label=None, text=None,
             test_id=None):
        step, desc = _selector_step(css, role, name, label, text, test_id)
        return Element(self._page, self._steps + [step], desc)


class Page:
    def __init__(self, session, page_id):
        self._session = session
        self._id = page_id

    def _call(self, method, *params):
        return self._session._call("page", page=self._id, method=method,
                                   params=list(params))

    def find(self, css=None, *, role=None, name=None, label=None, text=None,
             test_id=None):
        step, desc = _selector_step(css, role, name, label, text, test_id)
        return Element(self, [step], desc)

    def press(self, key):
        return self._call("press", key)

    def set_size(self, width, height):
        return self._call("set_size", width, height)

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
        return Path(self._call("screenshot", name))


class Session:
    def __init__(self, repo_root, work_dir):
        self._repo_root = Path(repo_root)
        self._work_dir = Path(work_dir)
        self._proc = None
        self._lines = None

    def _start(self):
        env_dir = _env_dir(self._repo_root)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self._work_dir),
            "PLAYWRIGHT_BROWSERS_PATH": str(env_dir / "browsers"),
        }
        self._proc = subprocess.Popen(
            [str(env_dir / "bin" / "python"), str(_HELPER),
             str(self._work_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            env=env, cwd=str(self._work_dir))
        self._lines = queue.Queue()
        stdout, lines = self._proc.stdout, self._lines

        def read():
            for line in stdout:
                lines.put(line)

        threading.Thread(target=read, daemon=True).start()

    def _kill(self):
        self._proc.kill()
        self._proc.wait()
        self._proc = None

    def _call(self, op, **args):
        if self._proc is None:
            self._start()
        self._proc.stdin.write(json.dumps({"op": op, "args": args}) + "\n")
        self._proc.stdin.flush()
        try:
            line = self._lines.get(timeout=_TIMEOUT)
        except queue.Empty:
            self._kill()
            raise BrowserError("timed out after 30 seconds") from None
        resp = json.loads(line)
        if not resp["ok"]:
            raise BrowserError(resp["error"])
        return resp["value"]

    def open(self, target, *, width=1280, height=800, color_scheme="light"):
        if color_scheme not in ("light", "dark"):
            raise BrowserError(
                f"color_scheme is light or dark: {color_scheme}")
        if isinstance(target, str) and urlsplit(target).scheme:
            parts = urlsplit(target)
            if parts.scheme != "http" or parts.hostname not in _LOOPBACK:
                raise BrowserError(
                    "only file paths and loopback URLs can be opened: "
                    f"{target}")
            url, root = target, None
        elif isinstance(target, (str, Path)):
            path = Path(target)
            if not path.is_absolute():
                path = self._work_dir / path
            if not path.is_file():
                raise BrowserError(f"no such file: {path}")
            url, root = path.as_uri(), str(path.parent)
        else:
            raise BrowserError(
                f"only file paths and loopback URLs can be opened: {target}")
        page_id = self._call("open", url=url, root=root, width=width,
                             height=height, color_scheme=color_scheme)
        return Page(self, page_id)

    def close(self):
        if self._proc is None:
            return
        try:
            self._call("close")
        finally:
            if self._proc is not None:
                self._kill()


def open_session(repo_root, work_dir):
    return Session(repo_root, work_dir)
