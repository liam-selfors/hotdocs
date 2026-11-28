"""Adapter for the `javascript` asset kind."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

KIND = "javascript"
GATE_VERSION = "kind-javascript@1.0.0"

_NEEDS = "javascript needs node >= 24"
_TIMEOUT = 30
_TIMED_OUT = "timed out after 30 seconds"

_DRIVER = "let r,[,,f,e,a]=process.argv;try{let g=(await import(f))[e];r=typeof g=='function'?{v:await g(...JSON.parse(a))}:{e:'no export '+e}}catch(x){r={e:''+(x?.message??x)}}console.log(JSON.stringify(r))"

_NAMES = "console.log(JSON.stringify(Object.keys(await import(process.argv[2]))))"

_OPERATORS = (
    ">>>=",
    "===", "!==", ">>>", "**=", "...", "<<=", ">>=", "&&=", "||=", "??=",
    "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "++", "--", "+=", "-=",
    "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>", "?.",
)

_SWAPS = {
    "===": "!==",
    "!==": "===",
    "==": "!=",
    "!=": "==",
    "<": ">=",
    ">=": "<",
    ">": "<=",
    "<=": ">",
    "&&": "||",
    "||": "&&",
}

_BOOL_SWAPS = {"true": "false", "false": "true"}

_ARITH_SWAPS = {"+": "-", "-": "+"}

_UNARY_KEYWORDS = frozenset((
    "return", "typeof", "void", "delete", "throw", "new", "in", "of",
    "instanceof", "case", "do", "else", "yield", "await",
))

_NAME_START = re.compile(r"[A-Za-z_$]")
_NAME_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER_RE = re.compile(r"[0-9][A-Za-z0-9_.]*")
_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

_TEST_AUTHOR_GUIDANCE = "\n".join((
    "Call the asset only through the `asset_runner` fixture:",
    "`run = asset_runner(\"<declared path>\")`, then `run(\"<export>\", [args])`,",
    "and compare the returned JSON with exact expected values. Every argument",
    "is plain JSON (dicts, lists, strings, numbers, booleans, `None`). Never",
    "start `node` yourself or search the `.js` file's text for words: a test",
    "that passes because a word is present checks nothing. Reading the file",
    "is allowed only to compare its whole text with something that must",
    "contain it verbatim, such as a page that inlines it. An",
    "export that takes a DOM object, such as `init(document)`, is not called",
    "by tests. Catch failures as `pytest.raises(Exception, match=...)` on the",
    "thrown message; the exception type is the adapter's.",
))

_GENERATOR_GUIDANCE = "\n".join((
    "Write the asset as an ES module of pure functions over JSON values,",
    "each exported with `export function <name>(...)`, plus at most one",
    "export `init(document)` that only wires browser events to those",
    "functions: `init` contains no comparison, logical or arithmetic",
    "operator, no `true` or `false` and no condition, so every decision, and",
    "every mutation site, is in a pure export that tests call. No imports, no network, no `eval`, no globals beyond the",
    "module's own, and no regular expression literals (write",
    "`new RegExp(\"...\")`), which the strength check's scan does not read.",
    "The text `</script` appears nowhere in the file, so a page can inline it.",
    "A page using the asset inlines its text in",
    "`<script type=\"module\">` followed by `init(document);`.",
))


class AssetError(Exception):
    """Failure of a javascript asset or of Node."""


def _node():
    return shutil.which("node")


def _run_node(node, args):
    return subprocess.run(
        [node] + [str(a) for a in args],
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _mkdtemp():
    return Path(tempfile.mkdtemp()).resolve()


def _last_nonempty(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _read_text(asset_file):
    return Path(asset_file).read_bytes().decode("utf-8")


def _scan(text):
    """Return a list of (kind, token, offset) tuples."""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"`":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                elif text[j] == c:
                    j += 1
                    break
                else:
                    j += 1
            j = min(j, n)
            tokens.append(("string", text[i:j], i))
            i = j
            continue
        if _NAME_START.match(c):
            m = _NAME_RE.match(text, i)
            tokens.append(("name", m.group(0), i))
            i = m.end()
            continue
        if c.isdigit() and c in "0123456789":
            m = _NUMBER_RE.match(text, i)
            tokens.append(("number", m.group(0), i))
            i = m.end()
            continue
        op = c
        for candidate in _OPERATORS:
            if text.startswith(candidate, i):
                op = candidate
                break
        tokens.append(("op", op, i))
        i += len(op)
    return tokens


def _line(text, offset):
    return 1 + text.count("\n", 0, offset)


def layout_errors(asset_file):
    asset_file = Path(asset_file)
    raw = asset_file.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["parse error: not UTF-8"]
    errors = []
    node = _node()
    if node is None:
        errors.append(_NEEDS)
    else:
        tmp = _mkdtemp()
        try:
            copy = tmp / (asset_file.stem + ".mjs")
            copy.write_bytes(raw)
            try:
                proc = _run_node(node, ["--check", copy])
            except subprocess.TimeoutExpired:
                errors.append("parse error: " + _TIMED_OUT)
            else:
                if proc.returncode != 0:
                    lines = (proc.stderr or "").splitlines()
                    chosen = ""
                    for line in lines:
                        if line.startswith("SyntaxError:"):
                            chosen = line
                            break
                    else:
                        for line in lines:
                            if line.strip():
                                chosen = line
                                break
                    errors.append("parse error: " + chosen.strip())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    tokens = _scan(text)
    for index, (kind, tok, _offset) in enumerate(tokens):
        if kind != "name":
            continue
        if tok == "import":
            errors.append("forbidden: import")
        elif tok in ("require", "fetch"):
            nxt = tokens[index + 1] if index + 1 < len(tokens) else None
            if nxt is not None and nxt[0] == "op" and nxt[1] == "(":
                errors.append("forbidden: " + tok + "(")
        elif tok in ("XMLHttpRequest", "WebSocket"):
            errors.append("forbidden: " + tok)
    return errors


def surface(asset_file):
    node = _node()
    if node is None:
        return {"names": []}
    tmp = _mkdtemp()
    try:
        copy = tmp / "asset.mjs"
        shutil.copyfile(Path(asset_file), copy)
        script = tmp / "names.mjs"
        script.write_text(_NAMES, encoding="utf-8")
        try:
            proc = _run_node(node, [
                "--permission",
                "--allow-fs-read=" + str(copy),
                "--allow-fs-read=" + str(script),
                script,
                copy,
            ])
        except subprocess.TimeoutExpired:
            return {"names": []}
        if proc.returncode != 0:
            return {"names": []}
        try:
            value = json.loads(_last_nonempty(proc.stdout))
        except ValueError:
            return {"names": []}
        if not isinstance(value, list):
            return {"names": []}
        return {"names": sorted(value)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _provision_result(ok, reason, versions):
    return {
        "ok": ok,
        "reason": reason,
        "versions": versions,
        "lockfile_sha256": None,
    }


def provision(repo_root):
    node = _node()
    if node is None:
        return _provision_result(False, _NEEDS, {})
    failed = "javascript environment: node --version failed"
    try:
        proc = _run_node(node, ["--version"])
    except subprocess.TimeoutExpired:
        return _provision_result(False, failed, {})
    if proc.returncode != 0:
        return _provision_result(False, failed, {})
    out = (proc.stdout or "").strip()
    version = out[1:] if out.startswith("v") else out
    if not _VERSION_RE.fullmatch(version):
        return _provision_result(
            False, "javascript environment: node --version printed " + out, {}
        )
    if int(version.split(".")[0]) < 24:
        return _provision_result(False, _NEEDS, {})
    return _provision_result(True, "", {"node": version})


def asset_runner(asset_file):
    asset_file = Path(asset_file)

    def run(entry, args):
        node = _node()
        if node is None:
            raise AssetError(_NEEDS)
        tmp = _mkdtemp()
        try:
            copy = tmp / "asset.mjs"
            shutil.copyfile(asset_file, copy)
            driver = tmp / "driver.mjs"
            driver.write_text(_DRIVER, encoding="utf-8")
            try:
                proc = _run_node(node, [
                    "--permission",
                    "--allow-fs-read=" + str(copy),
                    "--allow-fs-read=" + str(driver),
                    driver,
                    copy,
                    entry,
                    json.dumps(args),
                ])
            except subprocess.TimeoutExpired:
                raise AssetError(_TIMED_OUT)
            try:
                result = json.loads(_last_nonempty(proc.stdout))
            except ValueError:
                result = None
            if not isinstance(result, dict):
                raise AssetError(
                    "node exited %s: %s"
                    % (proc.returncode, _last_nonempty(proc.stderr))
                )
            if "v" in result:
                return result["v"]
            if "e" in result:
                raise AssetError(result["e"])
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return run


def _is_binary_context(prev):
    if prev is None:
        return False
    kind, tok, _offset = prev
    if kind == "number":
        return True
    if kind == "op":
        return tok in (")", "]")
    if kind == "name":
        return tok not in _UNARY_KEYWORDS
    return False


def strength_sites(asset_file):
    text = _read_text(asset_file)
    tokens = _scan(text)
    sites = []
    for index, (kind, tok, offset) in enumerate(tokens):
        swap = None
        if kind == "op":
            if tok in _SWAPS:
                swap = _SWAPS[tok]
            elif tok in _ARITH_SWAPS:
                prev = tokens[index - 1] if index > 0 else None
                if _is_binary_context(prev):
                    swap = _ARITH_SWAPS[tok]
        elif kind == "name" and tok in _BOOL_SWAPS:
            swap = _BOOL_SWAPS[tok]
        if swap is None:
            continue
        sites.append({
            "description": "%d: %s -> %s" % (_line(text, offset), tok, swap),
            "offset": offset,
            "token": tok,
            "swap": swap,
        })
    return sites


def apply_site(asset_file, site):
    asset_file = Path(asset_file)
    text = _read_text(asset_file)
    offset = site["offset"]
    token = site["token"]
    if text[offset:offset + len(token)] != token:
        raise ValueError(
            "site token %r not found at offset %d" % (token, offset)
        )
    new_text = text[:offset] + site["swap"] + text[offset + len(token):]
    asset_file.write_bytes(new_text.encode("utf-8"))


def guidance():
    return {
        "generator": _GENERATOR_GUIDANCE,
        "test_author": _TEST_AUTHOR_GUIDANCE,
    }
