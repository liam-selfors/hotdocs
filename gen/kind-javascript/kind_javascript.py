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


class AssetError(Exception):
    """A failure of the asset or of Node."""


_NEEDS = "javascript needs node >= 24"
_TIMEOUT = 30

_DRIVER = "let r,[,,f,e,a]=process.argv;try{let g=(await import(f))[e];r=typeof g=='function'?{v:await g(...JSON.parse(a))}:{e:'no export '+e}}catch(x){r={e:''+(x?.message??x)}}console.log(JSON.stringify(r))"

_NAMES = "console.log(JSON.stringify(Object.keys(await import(process.argv[2]))))"

_GENERATOR = """Write the asset as an ES module of pure functions over JSON values,
each exported with `export function <name>(...)`, plus at most one
export `init(document)` that only wires browser events to those
functions: `init` contains no comparison, logical or arithmetic
operator, no `true` or `false` and no condition, so every decision, and
every mutation site, is in a pure export that tests call. No imports, no network, no `eval`, no globals beyond the
module's own, and no regular expression literals (write
`new RegExp("...")`), which the strength check's scan does not read.
The text `</script` appears nowhere in the file, so a page can inline it.
A page using the asset inlines its text in
`<script type="module">` followed by `init(document);`."""

_TEST_AUTHOR = """Call the asset only through the `asset_runner` fixture:
`run = asset_runner("<declared path>")`, then `run("<export>", [args])`,
and compare the returned JSON with exact expected values. Every argument
is plain JSON (dicts, lists, strings, numbers, booleans, `None`). Never
start `node` yourself or search the `.js` file's text for words: a test
that passes because a word is present checks nothing. Reading the file
is allowed only to compare its whole text with something that must
contain it verbatim, such as a page that inlines it. An
export that takes a DOM object, such as `init(document)`, is not called
by tests. Catch failures as `pytest.raises(Exception, match=...)` on the
thrown message; the exception type is the adapter's."""

_OPS = sorted(
    [
        ">>>=", "===", "!==", ">>>", "**=", "...", "<<=", ">>=", "&&=", "||=",
        "??=", "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "++", "--",
        "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>", "?.",
    ],
    key=len,
    reverse=True,
)

_NAME_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUM_RE = re.compile(r"[0-9][A-Za-z0-9_.]*")
_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

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
    "+": "-",
    "-": "+",
}
_BOOL_SWAPS = {"true": "false", "false": "true"}

_UNARY_KEYWORDS = {
    "return", "typeof", "void", "delete", "throw", "new", "in", "of",
    "instanceof", "case", "do", "else", "yield", "await",
}


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
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            tokens.append(("string", text[i:j], i))
            i = j
            continue
        m = _NAME_RE.match(text, i)
        if m:
            tokens.append(("name", m.group(0), i))
            i = m.end()
            continue
        m = _NUM_RE.match(text, i)
        if m:
            tokens.append(("number", m.group(0), i))
            i = m.end()
            continue
        op = next((o for o in _OPS if text.startswith(o, i)), c)
        tokens.append(("op", op, i))
        i += len(op)
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


def _tmpdir():
    return Path(tempfile.mkdtemp()).resolve()


def _nonempty(lines_text):
    return [line.strip() for line in lines_text.splitlines() if line.strip()]


def layout_errors(asset_file):
    asset_file = Path(asset_file)
    data = asset_file.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["parse error: not UTF-8"]

    errors = []
    node = shutil.which("node")
    if node is None:
        errors.append(_NEEDS)
    else:
        tmp = _tmpdir()
        try:
            copy = tmp / (asset_file.stem + ".mjs")
            copy.write_bytes(data)
            try:
                proc = _run_node([node, "--check", str(copy)])
            except subprocess.TimeoutExpired:
                errors.append("parse error: timed out after 30 seconds")
            else:
                if proc.returncode != 0:
                    lines = _nonempty(proc.stderr or "")
                    line = next(
                        (l for l in lines if l.startswith("SyntaxError:")),
                        lines[0] if lines else "",
                    )
                    errors.append("parse error: " + line)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    tokens = _scan(text)
    for idx, (kind, tok, _offset) in enumerate(tokens):
        if kind != "name":
            continue
        if tok in ("import", "XMLHttpRequest", "WebSocket"):
            errors.append("forbidden: " + tok)
        elif tok in ("require", "fetch"):
            nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
            if nxt is not None and nxt[0] == "op" and nxt[1] == "(":
                errors.append("forbidden: " + tok + "(")
    return errors


def surface(asset_file):
    asset_file = Path(asset_file)
    names = []
    node = shutil.which("node")
    if node is None:
        return {"names": names}
    tmp = _tmpdir()
    try:
        copy = tmp / "asset.mjs"
        shutil.copyfile(asset_file, copy)
        script = tmp / "names.mjs"
        script.write_text(_NAMES, encoding="utf-8")
        cmd = [
            node,
            "--permission",
            "--allow-fs-read=" + str(copy),
            "--allow-fs-read=" + str(script),
            str(script),
            str(copy),
        ]
        try:
            proc = _run_node(cmd)
        except subprocess.TimeoutExpired:
            return {"names": names}
        if proc.returncode != 0:
            return {"names": names}
        lines = _nonempty(proc.stdout or "")
        if not lines:
            return {"names": names}
        try:
            value = json.loads(lines[-1])
        except ValueError:
            return {"names": names}
        if isinstance(value, list):
            names = sorted(str(v) for v in value)
        return {"names": names}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def provision(repo_root):
    def fail(reason):
        return {"ok": False, "reason": reason, "versions": {}, "lockfile_sha256": None}

    node = shutil.which("node")
    if node is None:
        return fail(_NEEDS)
    try:
        proc = _run_node([node, "--version"])
    except subprocess.TimeoutExpired:
        return fail("javascript environment: node --version failed")
    if proc.returncode != 0:
        return fail("javascript environment: node --version failed")
    out = (proc.stdout or "").strip()
    version = out[1:] if out.startswith("v") else out
    if not _VERSION_RE.fullmatch(version):
        return fail("javascript environment: node --version printed " + out)
    if int(version.split(".")[0]) < 24:
        return fail(_NEEDS)
    return {"ok": True, "reason": "", "versions": {"node": version}, "lockfile_sha256": None}


def asset_runner(asset_file):
    asset_file = Path(asset_file)

    def run(entry, args):
        node = shutil.which("node")
        if node is None:
            raise AssetError(_NEEDS)
        tmp = _tmpdir()
        try:
            copy = tmp / "asset.mjs"
            shutil.copyfile(asset_file, copy)
            driver = tmp / "driver.mjs"
            driver.write_text(_DRIVER, encoding="utf-8")
            cmd = [
                node,
                "--permission",
                "--allow-fs-read=" + str(copy),
                "--allow-fs-read=" + str(driver),
                str(driver),
                str(copy),
                entry,
                json.dumps(args),
            ]
            try:
                proc = _run_node(cmd)
            except subprocess.TimeoutExpired:
                raise AssetError("timed out after 30 seconds")
            lines = _nonempty(proc.stdout or "")
            obj = None
            if lines:
                try:
                    obj = json.loads(lines[-1])
                except ValueError:
                    obj = None
            if not isinstance(obj, dict):
                err_lines = _nonempty(proc.stderr or "")
                last = err_lines[-1] if err_lines else ""
                raise AssetError("node exited %s: %s" % (proc.returncode, last))
            if "v" in obj:
                return obj["v"]
            if "e" in obj:
                raise AssetError(obj["e"])
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return run


def strength_sites(asset_file):
    text = Path(asset_file).read_bytes().decode("utf-8")
    tokens = _scan(text)
    sites = []
    for idx, (kind, tok, offset) in enumerate(tokens):
        swap = None
        if kind == "name":
            swap = _BOOL_SWAPS.get(tok)
        elif kind == "op":
            swap = _SWAPS.get(tok)
            if tok in ("+", "-"):
                prev = tokens[idx - 1] if idx > 0 else None
                binary = prev is not None and (
                    prev[0] == "number"
                    or (prev[0] == "op" and prev[1] in (")", "]"))
                    or (prev[0] == "name" and prev[1] not in _UNARY_KEYWORDS)
                )
                if not binary:
                    swap = None
        if swap is None:
            continue
        line = 1 + text.count("\n", 0, offset)
        sites.append(
            {
                "description": "%d: %s -> %s" % (line, tok, swap),
                "offset": offset,
                "token": tok,
                "swap": swap,
            }
        )
    return sites


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def apply_site(asset_file, site):
    asset_file = Path(asset_file)
    text = asset_file.read_bytes().decode("utf-8")
    offset = _get(site, "offset")
    token = _get(site, "token")
    swap = _get(site, "swap")
    if text[offset:offset + len(token)] != token:
        raise ValueError("site token %r not found at offset %d" % (token, offset))
    new_text = text[:offset] + swap + text[offset + len(token):]
    asset_file.write_bytes(new_text.encode("utf-8"))


def guidance():
    return {"generator": _GENERATOR.strip(), "test_author": _TEST_AUTHOR.strip()}
