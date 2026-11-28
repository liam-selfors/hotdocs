"""Helper process for the `browser` test driver. Runs under the driver
environment's interpreter, the only process that imports Playwright; reads
one JSON request per line on stdin and writes one JSON reply per line."""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
ACTIONS = {"click", "dblclick", "hover", "fill", "press", "select", "check",
           "uncheck", "wheel", "drag_by"}
LISTS = {"console_errors": "errors", "blocked_requests": "blocked",
         "dialogs": "dialogs", "downloads": "downloads"}


class Fail(Exception):
    pass


def chromium_version():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        print(browser.version)
        browser.close()


def two_frames(page):
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame("
        "() => requestAnimationFrame(() => r())))")


def allowed(url, root):
    parts = urlsplit(url)
    if parts.scheme in ("data", "blob"):
        return True
    if parts.scheme == "http":
        return parts.hostname in LOOPBACK
    if parts.scheme == "file" and root is not None:
        path = os.path.normpath(url2pathname(parts.path))
        return path == root or path.startswith(root.rstrip(os.sep) + os.sep)
    return False


def centre(loc):
    b = loc.bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


class Driver:
    def __init__(self, work_dir):
        from playwright.sync_api import sync_playwright
        self.work_dir = Path(work_dir)
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.context = self.browser.new_context(
            locale="en-US", timezone_id="UTC", device_scale_factor=1,
            reduced_motion="reduce", service_workers="block",
            accept_downloads=True)
        self.pages = []

    def handle(self, req):
        op, a = req["op"], req["args"]
        if op == "open":
            return self.open(**a)
        if op == "close":
            return self.close()
        if op == "page":
            return self.page_op(a["page"], a["method"], a["params"])
        return self.element_op(a["page"], a["steps"], a["desc"],
                               a["method"], a["params"])

    def open(self, url, root, width, height, color_scheme):
        root = os.path.normpath(root) if root is not None else None
        page = self.context.new_page()
        st = {"page": page, "errors": [], "blocked": [], "dialogs": [],
              "downloads": []}

        def on_console(msg):
            if msg.type == "error":
                st["errors"].append(msg.text)

        def on_pageerror(err):
            st["errors"].append(f"{err.name}: {err.message}")

        def on_dialog(dialog):
            st["dialogs"].append(dialog.message)
            dialog.accept()

        def on_download(download):
            target = self.work_dir / "downloads" / download.suggested_filename
            target.parent.mkdir(parents=True, exist_ok=True)
            download.save_as(str(target))
            st["downloads"].append(str(target))

        def on_route(route):
            request_url = route.request.url
            if allowed(request_url, root):
                route.continue_()
            else:
                st["blocked"].append(request_url)
                route.abort()

        page.route("**/*", on_route)
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("dialog", on_dialog)
        page.on("download", on_download)
        page.set_viewport_size({"width": width, "height": height})
        page.emulate_media(color_scheme=color_scheme, reduced_motion="reduce")
        page.goto(url, wait_until="load")
        two_frames(page)
        self.pages.append(st)
        return len(self.pages) - 1

    def close(self):
        n = 0
        for st in self.pages:
            page = st["page"]
            if page.is_closed():
                continue
            n += 1
            try:
                path = self.work_dir / "screenshots" / f"final-{n}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(path), full_page=True)
            except Exception:
                pass
        self.browser.close()
        self.pw.stop()
        return None

    def page_op(self, pid, method, params):
        st = self.pages[pid]
        page = st["page"]
        if method in LISTS:
            return list(st[LISTS[method]])
        if method == "press":
            page.keyboard.press(params[0])
            two_frames(page)
            return None
        if method == "set_size":
            page.set_viewport_size({"width": params[0], "height": params[1]})
            two_frames(page)
            return None
        if method == "url":
            return page.url
        if method == "title":
            return page.title()
        path = self.work_dir / "screenshots" / f"{params[0]}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=True)
        return str(path)

    def locate(self, page, steps):
        loc = page
        for s in steps:
            if "nth" in s:
                loc = loc.nth(s["nth"])
                continue
            kind, value = s["kind"], s["value"]
            if kind == "css":
                loc = loc.locator(value)
            elif kind == "role":
                loc = loc.get_by_role(value, name=s.get("name"), exact=True)
            elif kind == "label":
                loc = loc.get_by_label(value, exact=True)
            elif kind == "text":
                loc = loc.get_by_text(value, exact=True)
            else:
                loc = loc.get_by_test_id(value)
        return loc

    def single(self, page, loc, desc, action):
        deadline = time.monotonic() + 5
        while True:
            n = loc.count()
            if n == 1 and loc.is_visible() and (not action or loc.is_enabled()):
                return
            if time.monotonic() >= deadline:
                if n > 1:
                    raise Fail(f"{n} elements match {desc}")
                raise Fail(f"no element matches {desc}")
            page.wait_for_timeout(50)

    def element_op(self, pid, steps, desc, method, params):
        page = self.pages[pid]["page"]
        loc = self.locate(page, steps)
        if method == "count":
            return loc.count()
        if method == "texts":
            return [t.strip() for t in loc.all_inner_texts()]
        if method == "visible":
            return any(loc.nth(i).is_visible() for i in range(loc.count()))
        action = method in ACTIONS
        self.single(page, loc, desc, action)
        if not action:
            if method == "text":
                return loc.inner_text().strip()
            if method == "value":
                return loc.input_value()
            if method == "attribute":
                return loc.get_attribute(params[0])
            if method == "checked":
                return loc.is_checked()
            if method == "box":
                b = loc.bounding_box()
                return {k: round(b[k]) for k in ("x", "y", "width", "height")}
            return loc.evaluate(
                "(e, p) => getComputedStyle(e).getPropertyValue(p)",
                params[0]).strip()
        if method == "click":
            loc.click(modifiers=params[0], timeout=5000)
        elif method == "dblclick":
            loc.dblclick(timeout=5000)
        elif method == "hover":
            loc.hover(timeout=5000)
        elif method == "fill":
            loc.fill(params[0], timeout=5000)
        elif method == "press":
            loc.press(params[0], timeout=5000)
        elif method == "select":
            loc.select_option(value=params[0], timeout=5000)
        elif method == "check":
            loc.check(timeout=5000)
        elif method == "uncheck":
            loc.uncheck(timeout=5000)
        elif method == "wheel":
            x, y = centre(loc)
            page.mouse.move(x, y)
            page.mouse.wheel(params[0], params[1])
        else:
            x, y = centre(loc)
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + params[0], y + params[1], steps=10)
            page.mouse.up()
        two_frames(page)
        return None


def main():
    if sys.argv[1:] == ["--chromium-version"]:
        chromium_version()
        return
    out = sys.stdout
    sys.stdout = sys.stderr
    work_dir = sys.argv[1]
    driver = None
    for line in sys.stdin:
        req = json.loads(line)
        try:
            if driver is None:
                driver = Driver(work_dir)
            resp = {"ok": True, "value": driver.handle(req)}
        except Exception as exc:
            resp = {"ok": False, "error": str(exc)}
        out.write(json.dumps(resp) + "\n")
        out.flush()
        if req["op"] == "close":
            break


if __name__ == "__main__":
    main()
