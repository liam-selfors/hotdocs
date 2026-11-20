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

_NEEDS = "javascript needs node >= 24"
_TIMEOUT = 30

_NAMES_SCRIPT = "console.log(JSON.stringify(Object.keys(await import(process.argv[2]))))"

_DRIVER = "let r,[,,f,e,a]=process.argv;try{let g=(await import(f))[e];r=typeof g=='function'?{v:await g(...JSON.parse(a))}:{e:'no export '+e}}catch(x){r={e:''+(x?.message??x)}}console.log(JSON.stringify(r))"

_OPERATORS = sorted(
    [
        ">>>=", "===", "!==", ">>>", "**=", "...", "<<=", ">>=", "&&=", "||=",
        "??=", "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "++", "--",
        "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>", "?.",
    ],
    key=len,
    reverse=True,
)

_NAME_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER_RE = re.compile(r"[0-9][A-Za-z0-9_.]*")

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

_GENERATOR_GUIDANCE = """Write the asset as an ES module of pure functions over JSON values,
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

_TEST_AUTHOR_GUIDANCE = """Call the asset only through the `asset_runner` fixture:
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


class AssetError(Exception):
    """A failure of the asset or of Node."""


def _scan(text):
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
            tokens.append(("name", m.group(), i))
            i = m.end()
            continue
        m = _NUMBER_RE.match(text, i)
        if m:
            tokens.append(("number", m.group(), i))
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


def _node_env():
    return {"PATH": os.environ.get("PATH", "")}


def _run_node(node, args):
    return subprocess.run(
        [node] + args,
        env=_node_env(),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _mkdtemp():
    return Path(tempfile.mkdtemp()).resolve()


def _last_nonempty(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _parse_error(asset_file, node):
    if node is None:
        return _NEEDS
    tmp = _mkdtemp()
    try:
        copy = tmp / (Path(asset_file).stem + ".mjs")
        shutil.copyfile(asset_file, copy)
        try:
            proc = _run_node(node, ["--check", str(copy)])
        except subprocess.TimeoutExpired:
            return "parse error: timed out after 30 seconds"
        if proc.returncode == 0:
            return None
        lines = [line.strip() for line in proc.stderr.splitlines()]
        chosen = next((line for line in lines if line.startswith("SyntaxError:")), None)
        if chosen is None:
            chosen = next((line for line in lines if line), "")
        return "parse error: " + chosen
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def layout_errors(asset_file):
    asset_file = Path(asset_file)
    try:
        text = asset_file.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return ["parse error: not UTF-8"]
    errors = []
    parse = _parse_error(asset_file, shutil.which("node"))
    if parse is not None:
        errors.append(parse)
    tokens = _scan(text)
    for index, (kind, value, _offset) in enumerate(tokens):
        if kind != "name":
            continue
        if value in ("import", "XMLHttpRequest", "WebSocket"):
            errors.append("forbidden: " + value)
        elif value in ("require", "fetch"):
            if index + 1 < len(tokens) and tokens[index + 1][1] == "(":
                errors.append("forbidden: " + value + "(")
    return errors


def surface(asset_file):
    node = shutil.which("node")
    if node is None:
        return {"names": []}
    tmp = _mkdtemp()
    try:
        copy = tmp / "asset.mjs"
        shutil.copyfile(Path(asset_file), copy)
        script = tmp / "names.mjs"
        script.write_text(_NAMES_SCRIPT, encoding="utf-8")
        try:
            proc = _run_node(
                node,
                [
                    "--permission",
                    "--allow-fs-read=" + str(copy),
                    "--allow-fs-read=" + str(script),
                    str(script),
                    str(copy),
                ],
            )
        except subprocess.TimeoutExpired:
            return {"names": []}
        if proc.returncode != 0:
            return {"names": []}
        try:
            names = json.loads(_last_nonempty(proc.stdout))
        except ValueError:
            return {"names": []}
        if not isinstance(names, list):
            return {"names": []}
        return {"names": sorted(names)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _provision_result(ok, reason, versions):
    return {"ok": ok, "reason": reason, "versions": versions, "lockfile_sha256": None}


def provision(repo_root):
    node = shutil.which("node")
    if node is None:
        return _provision_result(False, _NEEDS, {})
    try:
        proc = _run_node(node, ["--version"])
    except subprocess.TimeoutExpired:
        return _provision_result(False, "javascript environment: node --version failed", {})
    if proc.returncode != 0:
        return _provision_result(False, "javascript environment: node --version failed", {})
    stripped = proc.stdout.strip()
    version = stripped[1:] if stripped.startswith("v") else stripped
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        return _provision_result(
            False, "javascript environment: node --version printed " + stripped, {}
        )
    if int(version.split(".")[0]) < 24:
        return _provision_result(False, _NEEDS, {})
    return _provision_result(True, "", {"node": version})


def asset_runner(asset_file):
    asset_file = Path(asset_file)

    def run(entry, args):
        node = shutil.which("node")
        if node is None:
            raise AssetError(_NEEDS)
        tmp = _mkdtemp()
        try:
            copy = tmp / "asset.mjs"
            shutil.copyfile(asset_file, copy)
            driver = tmp / "driver.mjs"
            driver.write_text(_DRIVER, encoding="utf-8")
            try:
                proc = _run_node(
                    node,
                    [
                        "--permission",
                        "--allow-fs-read=" + str(copy),
                        "--allow-fs-read=" + str(driver),
                        str(driver),
                        str(copy),
                        entry,
                        json.dumps(args),
                    ],
                )
            except subprocess.TimeoutExpired:
                raise AssetError("timed out after 30 seconds")
            try:
                result = json.loads(_last_nonempty(proc.stdout))
            except ValueError:
                result = None
            if not isinstance(result, dict):
                raise AssetError(
                    "node exited %s: %s" % (proc.returncode, _last_nonempty(proc.stderr))
                )
            if "v" in result:
                return result["v"]
            if "e" in result:
                raise AssetError(result["e"])
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return run


def _swap_for(tokens, index):
    kind, value, _offset = tokens[index]
    if kind == "name":
        return _BOOL_SWAPS.get(value)
    if kind != "op":
        return None
    swap = _SWAPS.get(value)
    if value in ("+", "-"):
        if index == 0:
            return None
        prev_kind, prev_value, _ = tokens[index - 1]
        binary = (
            prev_kind == "number"
            or prev_value in (")", "]")
            or (prev_kind == "name" and prev_value not in _UNARY_KEYWORDS)
        )
        if not binary:
            return None
    return swap


def strength_sites(asset_file):
    text = Path(asset_file).read_bytes().decode("utf-8")
    tokens = _scan(text)
    sites = []
    for index, (_kind, value, offset) in enumerate(tokens):
        swap = _swap_for(tokens, index)
        if swap is None:
            continue
        line = text.count("\n", 0, offset) + 1
        sites.append(
            {
                "description": "%d: %s -> %s" % (line, value, swap),
                "offset": offset,
                "token": value,
                "swap": swap,
            }
        )
    return sites


def apply_site(asset_file, site):
    asset_file = Path(asset_file)
    text = asset_file.read_bytes().decode("utf-8")
    token = site["token"]
    offset = site["offset"]
    if text[offset:offset + len(token)] != token:
        raise ValueError("site token not found at offset %s" % offset)
    mutated = text[:offset] + site["swap"] + text[offset + len(token):]
    asset_file.write_bytes(mutated.encode("utf-8"))


def guidance():
    return {"generator": _GENERATOR_GUIDANCE, "test_author": _TEST_AUTHOR_GUIDANCE}
