"""Playwright side of driver_browser: run from the driver environment's
interpreter, it reads one JSON request per line on stdin and writes one
JSON reply per line on stdout."""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from playwright.sync_api import sync_playwright

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
FRAMES = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(null))))"
STYLE = "(e, p) => getComputedStyle(e).getPropertyValue(p)"


class HelperError(Exception):
    pass


def two_frames(page):
    page.evaluate(FRAMES)


def allowed(url, allowed_dir):
    parts = urlsplit(url)
    if parts.scheme in ("data", "blob"):
        return True
    if parts.scheme == "http":
        return parts.hostname in LOOPBACK
    if parts.scheme == "file" and allowed_dir is not None:
        return Path(url2pathname(parts.path)).resolve().is_relative_to(allowed_dir)
    return False


def build(page, steps):
    locator = page
    for step in steps:
        if "nth" in step:
            locator = locator.nth(step["nth"])
        elif step["kind"] == "css":
            locator = locator.locator(step["value"])
        elif step["kind"] == "role":
            locator = locator.get_by_role(step["value"], name=step["name"], exact=True)
        elif step["kind"] == "label":
            locator = locator.get_by_label(step["value"], exact=True)
        elif step["kind"] == "text":
            locator = locator.get_by_text(step["value"], exact=True)
        else:
            locator = locator.get_by_test_id(step["value"])
    return locator


def resolve(page, locator, selector, action):
    deadline = time.monotonic() + 5
    while True:
        matches = [
            match
            for match in locator.filter(visible=True).all()
            if not action or match.is_enabled()
        ]
        if len(matches) == 1:
            return matches[0]
        if time.monotonic() >= deadline:
            break
        page.wait_for_timeout(50)
    if not matches:
        raise HelperError(f"no element matches {selector}")
    raise HelperError(f"{len(matches)} elements match {selector}")


def wheel(page, target, dx, dy):
    target.hover()
    page.mouse.wheel(dx, dy)


def drag_by(page, target, dx, dy):
    target.hover()
    box = target.bounding_box()
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=10)
    page.mouse.up()


ACTIONS = {
    "click": lambda page, target, modifiers: target.click(modifiers=modifiers),
    "dblclick": lambda page, target: target.dblclick(),
    "hover": lambda page, target: target.hover(),
    "fill": lambda page, target, text: target.fill(text),
    "press": lambda page, target, key: target.press(key),
    "select": lambda page, target, value: target.select_option(value=value),
    "check": lambda page, target: target.check(),
    "uncheck": lambda page, target: target.uncheck(),
    "wheel": wheel,
    "drag_by": drag_by,
}


def read_box(target):
    box = target.bounding_box()
    return {key: round(box[key]) for key in ("x", "y", "width", "height")}


READS = {
    "text": lambda target: target.inner_text().strip(),
    "value": lambda target: target.input_value(),
    "attribute": lambda target, name: target.get_attribute(name),
    "checked": lambda target: target.is_checked(),
    "box": read_box,
    "style": lambda target, prop: target.evaluate(STYLE, prop).strip(),
}

MANY = {
    "count": lambda locator: locator.count(),
    "texts": lambda locator: [text.strip() for text in locator.all_inner_texts()],
    "visible": lambda locator: locator.filter(visible=True).count() > 0,
}


class Driven:
    def __init__(self, browser, work_dir, url, allowed_dir, width, height, color_scheme):
        self.work_dir = work_dir
        self.errors = []
        self.blocked = []
        self.dialog_messages = []
        self.saved = []
        self.pending = []
        self.allowed_dir = None if allowed_dir is None else Path(allowed_dir)
        self.context = browser.new_context(
            viewport={"width": width, "height": height},
            locale="en-US",
            timezone_id="UTC",
            device_scale_factor=1,
            reduced_motion="reduce",
            color_scheme=color_scheme,
            accept_downloads=True,
            service_workers="block",
        )
        self.context.set_default_timeout(5000)

        def on_route(route):
            request_url = route.request.url
            if allowed(request_url, self.allowed_dir):
                route.continue_()
            else:
                self.blocked.append(request_url)
                route.abort()

        def on_console(message):
            if message.type == "error":
                self.errors.append(message.text)

        def on_pageerror(error):
            self.errors.append(f"{error.name}: {error.message}")

        def on_dialog(dialog):
            self.dialog_messages.append(dialog.message)
            dialog.accept()

        def on_download(download):
            self.pending.append(download)

        self.context.route("**/*", on_route)
        self.page = self.context.new_page()
        self.page.on("console", on_console)
        self.page.on("pageerror", on_pageerror)
        self.page.on("dialog", on_dialog)
        self.page.on("download", on_download)
        self.page.goto(url, wait_until="load", timeout=0)
        two_frames(self.page)


class Helper:
    def __init__(self, browser, work_dir):
        self.browser = browser
        self.work_dir = work_dir
        self.pages = {}

    def handle(self, request):
        return getattr(self, "op_" + request["op"])(**request["args"])

    def op_open(self, url, allowed_dir, width, height, color_scheme):
        page_id = len(self.pages)
        self.pages[page_id] = Driven(
            self.browser, self.work_dir, url, allowed_dir, width, height, color_scheme
        )
        return page_id

    def op_press(self, page, key):
        driven = self.pages[page]
        driven.page.keyboard.press(key)
        two_frames(driven.page)

    def op_set_size(self, page, width, height):
        driven = self.pages[page]
        driven.page.set_viewport_size({"width": width, "height": height})
        two_frames(driven.page)

    def op_url(self, page):
        return self.pages[page].page.url

    def op_title(self, page):
        return self.pages[page].page.title()

    def op_console_errors(self, page):
        return list(self.pages[page].errors)

    def op_blocked_requests(self, page):
        return list(self.pages[page].blocked)

    def op_dialogs(self, page):
        return list(self.pages[page].dialog_messages)

    def op_downloads(self, page):
        driven = self.pages[page]
        folder = self.work_dir / "downloads"
        folder.mkdir(parents=True, exist_ok=True)
        pending, driven.pending = driven.pending, []
        for download in pending:
            target = folder / download.suggested_filename
            download.save_as(target)
            driven.saved.append(str(target))
        return list(driven.saved)

    def op_screenshot(self, page, name):
        folder = self.work_dir / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{name}.png"
        self.pages[page].page.screenshot(path=target, full_page=True)
        return str(target)

    def op_element(self, page, steps, selector, method, args):
        driven = self.pages[page]
        locator = build(driven.page, steps)
        if method in MANY:
            return MANY[method](locator)
        target = resolve(driven.page, locator, selector, method in ACTIONS)
        if method in ACTIONS:
            ACTIONS[method](driven.page, target, *args)
            two_frames(driven.page)
            return None
        return READS[method](target, *args)


def main():
    if sys.argv[1] == "--version":
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            print(browser.version)
            browser.close()
        return
    work_dir = Path(sys.argv[1])
    out = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        helper = Helper(browser, work_dir)
        for line in iter(sys.stdin.readline, ""):
            request = json.loads(line)
            try:
                reply = {"value": helper.handle(request)}
            except Exception as error:
                reply = {"error": str(error)}
            out.write(json.dumps(reply) + "\n")
            out.flush()
        browser.close()


if __name__ == "__main__":
    main()
