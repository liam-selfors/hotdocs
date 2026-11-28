"""Adapter for the `css` asset kind."""

import re
from pathlib import Path

KIND = "css"
GATE_VERSION = "kind-css@1.0.0"


class AssetError(Exception):
    """Raised by the callable `asset_runner` returns."""


_GENERATOR_GUIDANCE = """Write plain CSS: rules of selectors and declarations, `:root` custom
properties for every value a token names, and `@media` only one level
deep. No `@import`, `@font-face` or other at-rule, no `url(`, no
`expression(`, no `!important`, and no vendor hacks (a vendor-prefixed
font-family keyword such as `-apple-system` is a plain value, not a
hack). Write every
colour as `#rrggbb` in lowercase. The text `</style` appears nowhere in
the file, so a page can inline it."""

_TEST_AUTHOR_GUIDANCE = """Call the asset only through the `asset_runner` fixture:
`run = asset_runner("<declared path>")`, then `run("rule", [selector])`,
`run("tokens", [])`, `run("tokens", ["dark"])` or
`run("contrast", [a, b])`, and compare the result with exact expected
values. Never parse the `.css` file's text yourself or search it for
words: a test that passes because a word is present checks nothing.
Reading the file is allowed only to compare its whole text with
something that must contain it verbatim, such as a page that inlines
it, or to check that a text the layout forbids is absent. Catch failures as `pytest.raises(Exception, match=...)` on the
message; the exception type is the adapter's."""

_NAME_RE = re.compile(r"[A-Za-z0-9_-]*")
_CLASS_RE = re.compile(r"\.[A-Za-z_-][A-Za-z0-9_-]*")
_COLOUR_RE = re.compile(r"#[0-9a-fA-F]{6}")
_DARK = "(prefers-color-scheme: dark)"


def _read(asset_file):
    return Path(asset_file).read_bytes().decode("utf-8")


def _collapse(s):
    return re.sub(r"\s+", " ", s.strip())


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _lex(text):
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            yield "comment", i, j
        elif ch in "'\"":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            yield "string", i, j
        else:
            j = i + 1
            yield "code", i, j
        i = j


def _parse(text):
    """Return (first structural error message or None, rules)."""
    rules = []
    stack = []  # (kind, open_pos)
    buf = []  # (char, pos), comments removed
    colon = None
    media = None
    rule = None

    def err(pos, what):
        return "parse error: line %d: %s" % (_line(text, pos), what), rules

    def first_nonspace():
        for k, (c, _) in enumerate(buf):
            if not c.isspace():
                return k
        return None

    def clean(items):
        return "".join(c for c, _ in items)

    for kind, i, j in _lex(text):
        if kind == "comment":
            continue
        if kind == "string":
            buf.extend((text[k], k) for k in range(i, j))
            continue
        ch = text[i]
        if ch == "{":
            if stack and stack[-1][0] == "rule":
                return err(i, "unexpected {")
            prelude = clean(buf).strip()
            if prelude.startswith("@"):
                name = _NAME_RE.match(prelude, 1).group()
                at = buf[first_nonspace()][1]
                if name != "media":
                    return err(at, "at-rule @%s is not allowed" % name)
                if stack:
                    return err(at, "@media inside @media")
                media = _collapse(prelude[1 + len(name):])
                stack.append(("media", i))
            else:
                rule = {"prelude": _collapse(prelude), "media": media, "decls": []}
                rules.append(rule)
                stack.append(("rule", i))
            buf = []
            colon = None
        elif ch == "}":
            if not stack:
                return err(i, "unexpected }")
            if stack[-1][0] == "rule":
                message = _end_decl(text, buf, colon, rule, i, first_nonspace, clean)
                if message:
                    return message, rules
                rule = None
            else:
                media = None
            stack.pop()
            buf = []
            colon = None
        elif ch == ";":
            if not stack:
                prelude = clean(buf).strip()
                if prelude.startswith("@"):
                    name = _NAME_RE.match(prelude, 1).group()
                    return err(buf[first_nonspace()][1], "at-rule @%s is not allowed" % name)
                if prelude:
                    return err(i, "unexpected ;")
            elif stack[-1][0] == "media":
                return err(i, "unexpected ;")
            else:
                message = _end_decl(text, buf, colon, rule, i + 1, first_nonspace, clean)
                if message:
                    return message, rules
            buf = []
            colon = None
        else:
            if ch == ":" and colon is None and stack and stack[-1][0] == "rule":
                colon = len(buf)
            buf.append((ch, i))
    if stack:
        return err(stack[0][1], "unclosed {")
    return None, rules


def _end_decl(text, buf, colon, rule, end, first_nonspace, clean):
    k = first_nonspace()
    if k is None:
        return None
    if colon is None:
        return "parse error: line %d: expected :" % _line(text, buf[k][1])
    offset = buf[k][1]
    rule["decls"].append({
        "property": clean(buf[:colon]).strip(),
        "value": _collapse(clean(buf[colon + 1:])),
        "offset": offset,
        "end": end,
        "line": _line(text, offset),
    })
    return None


def _forbidden(text):
    mask = [False] * len(text)
    for kind, i, j in _lex(text):
        if kind == "code":
            mask[i] = True
    found = []
    lower = text.lower()
    for word in ("url(", "expression("):
        start = lower.find(word)
        while start >= 0:
            if all(mask[start:start + len(word)]):
                found.append((start, "forbidden: " + word))
            start = lower.find(word, start + 1)
    for m in re.finditer("</style", text, re.IGNORECASE):
        found.append((m.start(), "forbidden: </style"))
    found.sort()
    return [msg for _, msg in found]


def _load(asset_file):
    try:
        text = _read(asset_file)
    except UnicodeDecodeError:
        return ["parse error: not UTF-8"], []
    error, rules = _parse(text)
    errors = [error] if error else []
    return errors + _forbidden(text), rules


def layout_errors(asset_file):
    return _load(asset_file)[0]


def surface(asset_file):
    errors, rules = _load(asset_file)
    if errors:
        return {"names": []}
    names = set()
    for rule in rules:
        names.update(_CLASS_RE.findall(rule["prelude"]))
        if rule["media"] is None and rule["prelude"] == ":root":
            for decl in rule["decls"]:
                if decl["property"].startswith("--"):
                    names.add(decl["property"])
    return {"names": sorted(names)}


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {}, "lockfile_sha256": None}


def _tokens(rules, dark):
    tokens = {}
    for rule in rules:
        if rule["prelude"] != ":root":
            continue
        if dark:
            if rule["media"] != _DARK:
                continue
        elif rule["media"] is not None:
            continue
        for decl in rule["decls"]:
            if decl["property"].startswith("--"):
                tokens[decl["property"]] = decl["value"]
    return tokens


def _luminance(colour):
    total = 0.0
    for weight, start in ((0.2126, 1), (0.7152, 3), (0.0722, 5)):
        c = int(colour[start:start + 2], 16) / 255
        if c <= 0.04045:
            c = c / 12.92
        else:
            c = ((c + 0.055) / 1.055) ** 2.4
        total += weight * c
    return total


def asset_runner(asset_file):
    def run(entry, args):
        errors, rules = _load(asset_file)
        if errors:
            raise AssetError("invalid layout: " + errors[0])
        if entry == "tokens":
            if args:
                return _tokens(rules, True)
            return _tokens(rules, False)
        if entry == "rule":
            selector = args[0]
            matched = False
            result = {}
            for rule in rules:
                if rule["media"] is None and rule["prelude"] == selector:
                    matched = True
                    for decl in rule["decls"]:
                        result[decl["property"]] = decl["value"]
            if not matched:
                raise AssetError("no rule " + selector)
            return result
        if entry == "contrast":
            tokens = _tokens(rules, False)
            if len(args) > 2:
                tokens.update(_tokens(rules, True))
            lums = []
            for name in args[:2]:
                if name not in tokens:
                    raise AssetError("no token " + name)
                value = tokens[name]
                if not _COLOUR_RE.fullmatch(value):
                    raise AssetError("not a #rrggbb colour: " + name)
                lums.append(_luminance(value))
            lighter = max(lums)
            darker = min(lums)
            return round((lighter + 0.05) / (darker + 0.05), 2)
        raise AssetError("no entry " + entry)

    return run


def strength_sites(asset_file):
    errors, rules = _load(asset_file)
    if errors:
        return []
    sites = []
    for rule in rules:
        for decl in rule["decls"]:
            sites.append({
                "description": "%d: %s removed" % (decl["line"], decl["property"]),
                "offset": decl["offset"],
                "end": decl["end"],
                "property": decl["property"],
            })
    return sites


def apply_site(asset_file, site):
    text = _read(asset_file)
    if not text[site["offset"]:].startswith(site["property"]):
        raise ValueError("site does not match the file")
    new = text[:site["offset"]] + text[site["end"]:]
    Path(asset_file).write_bytes(new.encode("utf-8"))


def guidance():
    return {"generator": _GENERATOR_GUIDANCE, "test_author": _TEST_AUTHOR_GUIDANCE}
