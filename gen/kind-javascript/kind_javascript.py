"""Adapter for the ``javascript`` asset kind."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

KIND = "javascript"
GATE_VERSION = "kind-javascript@1.0.0"

_TIMEOUT = 30
_NEEDS = "javascript needs node >= 24"
_TIMED_OUT = "timed out after 30 seconds"

_NAMES_JS = "console.log(JSON.stringify(Object.keys(await import(process.argv[2]))))"
_DRIVER_JS = "let r,[,,f,e,a]=process.argv;try{let g=(await import(f))[e];r=typeof g=='function'?{v:await g(...JSON.parse(a))}:{e:'no export '+e}}catch(x){r={e:''+(x?.message??x)}}console.log(JSON.stringify(r))"

_OPERATORS = (
    ">>>=",
    "===", "!==", ">>>", "**=", "...", "<<=", ">>=", "&&=", "||=", "??=",
    "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "++", "--", "+=", "-=",
    "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>", "?.",
)

_SWAPS = {
    "===": "!==", "!==": "===",
    "==": "!=", "!=": "==",
    "<": ">=", ">=": "<",
    ">": "<=", "<=": ">",
    "&&": "||", "||": "&&",
}

_BOOL_SWAPS = {"true": "false", "false": "true"}
_ARITH_SWAPS = {"+": "-", "-": "+"}

_UNARY_KEYWORDS = frozenset((
    "return", "typeof", "void", "delete", "throw", "new", "in", "of",
    "instanceof", "case", "do", "else", "yield", "await",
))

_NAME_START = re.compile(r"[A-Za-z_$]")
_NAME_REST = re.compile(r"[A-Za-z0-9_$]*")
_NUMBER_REST = re.compile(r"[A-Za-z0-9_.]*")
_VERSION = re.compile(r"\d+\.\d+\.\d+")

_TEST_AUTHOR_LINES = (
    "Call the asset only through the `asset_runner` fixture:",
    '`run = asset_runner("<declared path>")`, then `run("<export>", [args])`,',
    "and compare the returned JSON with exact expected values. Every argument",
    "is plain JSON (dicts, lists, strings, numbers, booleans, `None`). Never",
    "start `node` yourself or search the `.js` file's text for words: a test",
    "that passes because a word is present checks nothing. Reading the file",
    "is allowed only to compare its whole text with something that must",
    "contain it verbatim, such as a page that inlines it. An",
    "export that takes a DOM object, such as `init(document)`, is not called",
    "by tests. Catch failures as `pytest.raises(Exception, match=...)` on the",
    "thrown message; the exception type is the adapter's.",
)

_GENERATOR_LINES = (
    "Write the asset as an ES module of pure functions over JSON values,",
    "each exported with `export function <name>(...)`, plus at most one",
    "export `init(document)` that only wires browser events to those",
    "functions: `init` contains no comparison, logical or arithmetic",
    "operator, no `true` or `false` and no condition, so every decision, and",
    "every mutation site, is in a pure export that tests call. No imports, no network, no `eval`, no globals beyond the",
    "module's own, and no regular expression literals (write",
    '`new RegExp("...")`), which the strength check\'s scan does not read.',
    "The text `</script` appears nowhere in the file, so a page can inline it.",
    "A page using the asset inlines its text in",
    '`<script type="module">` followed by `init(document);`.',
)


class AssetError(Exception):
    """A failure of the asset or of Node."""


def _scan(text):
    """Return a list of (kind, token, offset) in text order."""
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
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if c in "'\"`":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == c:
                    j += 1
                    break
                j += 1
            j = min(j, n)
            tokens.append(("string", text[i:j], i))
            i = j
            continue
        if _NAME_START.match(c):
            m = _NAME_REST.match(text, i + 1)
            tokens.append(("name", text[i:m.end()], i))
            i = m.end()
            continue
        if c.isdigit():
            m = _NUMBER_REST.match(text, i + 1)
            tokens.append(("number", text[i:m.end()], i))
            i = m.end()
            continue
        for op in _OPERATORS:
            if text.startswith(op, i):
                tokens.append(("op", op, i))
                i += len(op)
                break
        else:
            tokens.append(("op", c, i))
            i += 1
    return tokens


def _env():
    return {"PATH": os.environ.get("PATH", "")}


def _run_node(cmd):
    return subprocess.run(
        cmd,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _mkdtemp():
    return Path(tempfile.mkdtemp()).resolve()


def _non_empty_lines(output):
    return [line.strip() for line in (output or "").splitlines() if line.strip()]


def _last_json(output):
    lines = _non_empty_lines(output)
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except ValueError:
        return None


def layout_errors(asset_file):
    asset_file = Path(asset_file)
    data = asset_file.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["parse error: not UTF-8"]

    errors = []
    tmp = _mkdtemp()
    try:
        copy = tmp / (asset_file.stem + ".mjs")
        copy.write_bytes(data)
        node = shutil.which("node")
        if node is None:
            errors.append(_NEEDS)
        else:
            try:
                proc = _run_node([node, "--check", str(copy)])
            except subprocess.TimeoutExpired:
                errors.append("parse error: " + _TIMED_OUT)
            else:
                if proc.returncode != 0:
                    lines = _non_empty_lines(proc.stderr)
                    chosen = ""
                    for line in lines:
                        if line.startswith("SyntaxError:"):
                            chosen = line
                            break
                    else:
                        if lines:
                            chosen = lines[0]
                    errors.append("parse error: " + chosen)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tokens = _scan(text)
    for idx, (kind, tok, _offset) in enumerate(tokens):
        if kind != "name":
            continue
        if tok == "import":
            errors.append("forbidden: import")
        elif tok in ("require", "fetch"):
            if idx + 1 < len(tokens) and tokens[idx + 1][1] == "(" and tokens[idx + 1][0] == "op":
                errors.append("forbidden: " + tok + "(")
        elif tok in ("XMLHttpRequest", "WebSocket"):
            errors.append("forbidden: " + tok)
    return errors


def surface(asset_file):
    asset_file = Path(asset_file)
    names = []
    tmp = _mkdtemp()
    try:
        copy = tmp / "asset.mjs"
        shutil.copyfile(asset_file, copy)
        script = tmp / "names.mjs"
        script.write_text(_NAMES_JS, encoding="utf-8")
        node = shutil.which("node")
        if node is not None:
            try:
                proc = _run_node([
                    node,
                    "--permission",
                    "--allow-fs-read=" + str(copy),
                    "--allow-fs-read=" + str(script),
                    str(script),
                    str(copy),
                ])
            except subprocess.TimeoutExpired:
                proc = None
            if proc is not None and proc.returncode == 0:
                decoded = _last_json(proc.stdout)
                if isinstance(decoded, list):
                    names = sorted(decoded)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"names": names}


def _provision_result(ok, reason, versions):
    return {
        "ok": ok,
        "reason": reason,
        "versions": versions,
        "lockfile_sha256": None,
    }


def provision(repo_root):
    node = shutil.which("node")
    if node is None:
        return _provision_result(False, _NEEDS, {})
    try:
        proc = _run_node([node, "--version"])
    except subprocess.TimeoutExpired:
        return _provision_result(False, "javascript environment: node --version failed", {})
    if proc.returncode != 0:
        return _provision_result(False, "javascript environment: node --version failed", {})
    stripped = (proc.stdout or "").strip()
    version = stripped[1:] if stripped.startswith("v") else stripped
    if not _VERSION.fullmatch(version):
        return _provision_result(
            False, "javascript environment: node --version printed " + stripped, {}
        )
    if int(version.split(".")[0]) < 24:
        return _provision_result(False, _NEEDS, {})
    return _provision_result(True, "", {"node": version})


def asset_runner(asset_file):
    asset_file = Path(asset_file)

    def run(entry, args):
        tmp = _mkdtemp()
        try:
            copy = tmp / "asset.mjs"
            shutil.copyfile(asset_file, copy)
            driver = tmp / "driver.mjs"
            driver.write_text(_DRIVER_JS, encoding="utf-8")
            node = shutil.which("node")
            if node is None:
                raise AssetError(_NEEDS)
            try:
                proc = _run_node([
                    node,
                    "--permission",
                    "--allow-fs-read=" + str(copy),
                    "--allow-fs-read=" + str(driver),
                    str(driver),
                    str(copy),
                    entry,
                    json.dumps(args),
                ])
            except subprocess.TimeoutExpired:
                raise AssetError(_TIMED_OUT)
            result = _last_json(proc.stdout)
            if not isinstance(result, dict):
                err_lines = _non_empty_lines(proc.stderr)
                last = err_lines[-1] if err_lines else ""
                raise AssetError("node exited %s: %s" % (proc.returncode, last))
            if "v" in result:
                return result["v"]
            if "e" in result:
                raise AssetError(result["e"])
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return run


def _arith_is_binary(prev):
    kind, tok, _offset = prev
    if kind == "number":
        return True
    if kind == "op":
        return tok in (")", "]")
    if kind == "name":
        return tok not in _UNARY_KEYWORDS
    return False


def strength_sites(asset_file):
    text = Path(asset_file).read_bytes().decode("utf-8")
    tokens = _scan(text)
    sites = []
    for idx, (kind, tok, offset) in enumerate(tokens):
        swap = None
        if kind == "op" and tok in _SWAPS:
            swap = _SWAPS[tok]
        elif kind == "name" and tok in _BOOL_SWAPS:
            swap = _BOOL_SWAPS[tok]
        elif kind == "op" and tok in _ARITH_SWAPS:
            if idx > 0 and _arith_is_binary(tokens[idx - 1]):
                swap = _ARITH_SWAPS[tok]
        if swap is None:
            continue
        line = text.count("\n", 0, offset) + 1
        sites.append({
            "description": "%d: %s -> %s" % (line, tok, swap),
            "offset": offset,
            "token": tok,
            "swap": swap,
        })
    return sites


def apply_site(asset_file, site):
    asset_file = Path(asset_file)
    text = asset_file.read_bytes().decode("utf-8")
    offset = site["offset"]
    token = site["token"]
    if text[offset:offset + len(token)] != token:
        raise ValueError("site token %r not found at offset %d" % (token, offset))
    new_text = text[:offset] + site["swap"] + text[offset + len(token):]
    asset_file.write_bytes(new_text.encode("utf-8"))


def guidance():
    return {
        "generator": "\n".join(_GENERATOR_LINES).strip(),
        "test_author": "\n".join(_TEST_AUTHOR_LINES).strip(),
    }
