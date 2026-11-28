"""Helper process for driver_browser: runs Playwright, reading one JSON
request per line on stdin and writing one JSON reply per line on stdout."""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

LOOPBACK = ("127.0.0.1", "localhost", "::1")
FRAMES = ("() => new Promise(r => requestAnimationFrame("
          "() => requestAnimationFrame(() => r())))")
STYLE = "(e, p) => getComputedStyle(e).getPropertyValue(p)"
WAIT_SECONDS = 5


class LookupFailed(Exception):
    pass


def allowed(url, base_dir):
    parts = urlsplit(url)
    if parts.scheme in ("data", "blob"):
        return True
    if parts.scheme == "http":
        return parts.hostname in LOOPBACK
    if parts.scheme == "file" and base_dir is not None:
        path = os.path.normpath(unquote(parts.path))
        return path.startswith(base_dir + os.sep)
    return False


def frames(page):
    page.evaluate(FRAMES)


def squash(text):
    return " ".join(text.split())


class Driver:
    def __init__(self, work_dir):
        self.work_dir = Path(work_dir)
        self.playwright = None
        self.browser = None
        self.pages = []

    def handle(self, request):
        return getattr(self, "op_" + request["op"])(**request["args"])

    def op_open(self, url, base_dir, width, height, color_scheme):
        if self.browser is None:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch()
        if base_dir is not None:
            base_dir = os.path.normpath(base_dir)
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            color_scheme=color_scheme, locale="en-US", timezone_id="UTC",
            device_scale_factor=1, reduced_motion="reduce",
            service_workers="block", accept_downloads=True)
        page = context.new_page()
        rec = {"page": page, "errors": [], "blocked": [], "dialogs": [],
               "downloads": []}
        downloads_dir = self.work_dir / "downloads"

        def on_route(route):
            request_url = route.request.url
            if allowed(request_url, base_dir):
                route.continue_()
            else:
                rec["blocked"].append(request_url)
                route.abort()

        def on_console(message):
            if message.type == "error":
                rec["errors"].append(message.text)

        def on_pageerror(error):
            rec["errors"].append(f"{error.name}: {error.message}")

        def on_dialog(dialog):
            rec["dialogs"].append(dialog.message)
            dialog.accept()

        def on_download(download):
            downloads_dir.mkdir(parents=True, exist_ok=True)
            target = downloads_dir / download.suggested_filename
            download.save_as(str(target))
            rec["downloads"].append(str(target))

        page.route("**/*", on_route)
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("dialog", on_dialog)
        page.on("download", on_download)
        self.pages.append(rec)
        page.goto(url, wait_until="load")
        frames(page)
        return len(self.pages) - 1

    def _log(self, page, key):
        rec = self.pages[page]
        if not rec["page"].is_closed():
            rec["page"].evaluate("0")
        return list(rec[key])

    def op_press(self, page, key):
        p = self.pages[page]["page"]
        p.keyboard.press(key)
        frames(p)

    def op_set_size(self, page, width, height):
        p = self.pages[page]["page"]
        p.set_viewport_size({"width": width, "height": height})
        frames(p)

    def op_url(self, page):
        return self.pages[page]["page"].url

    def op_title(self, page):
        return self.pages[page]["page"].title()

    def op_console_errors(self, page):
        return self._log(page, "errors")

    def op_blocked_requests(self, page):
        return self._log(page, "blocked")

    def op_dialogs(self, page):
        return self._log(page, "dialogs")

    def op_downloads(self, page):
        return self._log(page, "downloads")

    def op_screenshot(self, page, name):
        target = self.work_dir / "screenshots" / f"{name}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        self.pages[page]["page"].screenshot(path=str(target), full_page=True)
        return str(target)

    def locate(self, page, chain):
        p = self.pages[page]["page"]
        loc = p
        for step in chain:
            kind = step["kind"]
            if kind == "nth":
                loc = loc.nth(step["index"])
            elif kind == "css":
                loc = loc.locator(step["value"])
            elif kind == "role":
                loc = loc.get_by_role(step["value"], name=step["name"], exact=True)
            elif kind == "label":
                loc = loc.get_by_label(step["value"], exact=True)
            elif kind == "text":
                loc = loc.get_by_text(step["value"], exact=True)
            else:
                loc = loc.get_by_test_id(step["value"])
        return p, loc

    @staticmethod
    def resolve(p, loc, selector, need):
        deadline = time.monotonic() + WAIT_SECONDS
        while True:
            matches = [loc.nth(i) for i in range(loc.count())]
            if need == "action":
                good = [m for m in matches
                        if m.is_visible() and m.is_enabled(timeout=1000)]
            elif need == "visible":
                good = [m for m in matches if m.is_visible()]
            else:
                good = matches
            if len(good) == 1:
                return good[0]
            if time.monotonic() >= deadline:
                if not good:
                    raise LookupFailed(f"no element matches {selector}")
                raise LookupFailed(f"{len(good)} elements match {selector}")
            p.wait_for_timeout(50)

    def op_act(self, page, chain, selector, action, args):
        p, loc = self.locate(page, chain)
        target = self.resolve(p, loc, selector, "action")
        if action == "click":
            target.click(modifiers=args["modifiers"], timeout=5000)
        elif action == "dblclick":
            target.dblclick(timeout=5000)
        elif action == "hover":
            target.hover(timeout=5000)
        elif action == "fill":
            target.fill(args["text"], timeout=5000)
        elif action == "press":
            target.press(args["key"], timeout=5000)
        elif action == "select":
            target.select_option(value=args["value"], timeout=5000)
        elif action == "check":
            target.check(timeout=5000)
        elif action == "uncheck":
            target.uncheck(timeout=5000)
        elif action == "wheel":
            target.hover(timeout=5000)
            p.mouse.wheel(args["dx"], args["dy"])
        else:
            target.hover(timeout=5000)
            box = target.bounding_box()
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            p.mouse.down()
            p.mouse.move(x + args["dx"], y + args["dy"], steps=10)
            p.mouse.up()
        frames(p)

    def op_read(self, page, chain, selector, read, args):
        p, loc = self.locate(page, chain)
        need = "attached" if read in ("attribute", "style") else "visible"
        target = self.resolve(p, loc, selector, need)
        if read == "text":
            return squash(target.inner_text())
        if read == "value":
            return target.input_value()
        if read == "attribute":
            return target.get_attribute(args["name"])
        if read == "checked":
            return target.is_checked()
        if read == "box":
            box = target.bounding_box()
            return {key: round(box[key]) for key in ("x", "y", "width", "height")}
        return target.evaluate(STYLE, args["property"]).strip()

    def op_all(self, page, chain, read):
        _, loc = self.locate(page, chain)
        if read == "count":
            return loc.count()
        if read == "texts":
            return [squash(text) for text in loc.all_inner_texts()]
        return any(loc.nth(i).is_visible() for i in range(loc.count()))

    def op_close(self):
        open_pages = [rec["page"] for rec in self.pages
                      if not rec["page"].is_closed()]
        shots = self.work_dir / "screenshots"
        for n, page in enumerate(open_pages, 1):
            try:
                shots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shots / f"final-{n}.png"), full_page=True)
            except Exception:
                pass
        self.browser.close()
        self.playwright.stop()


def chromium_version():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        print(browser.version)
        browser.close()


def main():
    if sys.argv[1] == "--chromium-version":
        chromium_version()
        return
    out = sys.stdout
    sys.stdout = sys.stderr
    driver = Driver(sys.argv[1])
    for line in sys.stdin:
        request = json.loads(line)
        try:
            reply = {"ok": True, "value": driver.handle(request)}
        except Exception as exc:
            reply = {"ok": False, "error": str(exc)}
        out.write(json.dumps(reply) + "\n")
        out.flush()
        if request["op"] == "close":
            break


if __name__ == "__main__":
    main()
