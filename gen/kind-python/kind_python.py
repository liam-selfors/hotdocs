"""Adapter for the `python` asset kind."""

import ast
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

KIND = "python"
GATE_VERSION = "kind-python@1.0.0"


class AssetError(Exception):
    """A failure of the asset's code or of its process."""


_SURFACE_PROGRAM = "\n".join([
    "import importlib,json,sys",
    "print('\\n'+json.dumps(sorted(n for n in dir(importlib.import_module(sys.argv[1])) if not n.startswith('_'))))",
])

_DRIVER = "\n".join([
    "import importlib,json,sys",
    "m,e,a=sys.argv[1:4]",
    "try:",
    " f=getattr(importlib.import_module(m),e,None)",
    " o=json.dumps({'v':f(*json.loads(a))} if callable(f) else {'e':'no entry '+e})",
    "except BaseException as x:",
    " o=json.dumps({'e':str(x)})",
    "print('\\n'+o)",
])

_VERSIONS_PROGRAM = "\n".join([
    "import hashlib,json,platform,re",
    "from importlib.metadata import distributions as ds",
    "s=sorted({re.sub(r'[-_.]+','-',str(d.metadata['Name']).lower())+'=='+str(d.version) for d in ds()})",
    r"print(json.dumps({'python':platform.python_version(),'packages':'sha256:'+hashlib.sha256('\n'.join(s).encode()).hexdigest()}))",
])

_SWAPS = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod, ast.Mod: ast.FloorDiv,
}


def _python_files(asset_file):
    rels = []
    for path in asset_file.rglob("*.py"):
        rel = path.relative_to(asset_file)
        if "__pycache__" in rel.parts or not path.is_file():
            continue
        rels.append("/".join(rel.parts))
    return sorted(rels)


def _module_name(asset_file):
    return asset_file.name.replace("-", "_")


def _interpreter():
    return os.environ.get("HOTDOCS_PYTHON") or sys.executable


def _nonempty_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _last_json(stdout):
    lines = _nonempty_lines(stdout)
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except ValueError:
        return None


def _last_stderr_line(stderr):
    lines = _nonempty_lines(stderr)
    return lines[-1] if lines else ""


def _run_code(asset_file, interpreter, program, args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(asset_file)
    return subprocess.run(
        [interpreter, "-c", program, *args],
        cwd=str(asset_file),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def layout_errors(asset_file: Path) -> list:
    errors = []
    for rel in _python_files(asset_file):
        data = (asset_file / rel).read_bytes()
        try:
            ast.parse(data)
        except SyntaxError as exc:
            errors.append(f"{rel}:{exc.lineno or 0}: SyntaxError: {exc.msg}")
        except ValueError as exc:
            errors.append(f"{rel}:{getattr(exc, 'lineno', None) or 0}: SyntaxError: {exc}")
    return errors


def surface(asset_file: Path) -> dict:
    try:
        proc = _run_code(asset_file, _interpreter(), _SURFACE_PROGRAM, [_module_name(asset_file)])
    except (OSError, subprocess.TimeoutExpired):
        return {"names": []}
    if proc.returncode != 0:
        return {"names": []}
    names = _last_json(proc.stdout)
    if not isinstance(names, list):
        return {"names": []}
    return {"names": names}


def _versions(interpreter, sha):
    try:
        proc = subprocess.run(
            [interpreter, "-I", "-c", _VERSIONS_PROGRAM],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _fail("python environment: python version check failed", sha)
    obj = _last_json(proc.stdout)
    if proc.returncode != 0 or not isinstance(obj, dict):
        return _fail("python environment: python version check failed", sha)
    return {
        "ok": True,
        "reason": "",
        "versions": obj,
        "lockfile_sha256": sha,
        "interpreter": interpreter,
    }


def _fail(reason, sha):
    return {
        "ok": False,
        "reason": reason,
        "versions": {},
        "lockfile_sha256": sha,
        "interpreter": None,
    }


def _pins_pytest(text):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-")):
            continue
        name = re.split(r"[=<>!~\[;@ ]", stripped, maxsplit=1)[0]
        if re.sub(r"[-_.]+", "-", name.lower()) == "pytest":
            return True
    return False


def _run_tool(program, cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return f"python environment: {program} timed out"
    if proc.returncode != 0:
        line = _last_stderr_line(proc.stderr) or f"{program} exited {proc.returncode}"
        return f"python environment: {line}"
    return None


def provision(repo_root: Path) -> dict:
    pyenv = repo_root / "environments" / "python"
    lock = pyenv / "requirements.lock"
    sha = None
    if lock.is_file():
        sha = "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest()

    pin_file = pyenv / "python-version"
    if pin_file.is_file():
        pin = pin_file.read_text(encoding="utf-8").strip()
        version = platform.python_version()
        if pin and not (version == pin or version.startswith(pin + ".")):
            return _fail(f"python environment: needs Python {pin}, found {version}", sha)

    if sha is None:
        return _versions(sys.executable, None)

    if not _pins_pytest(lock.read_text(encoding="utf-8")):
        return _fail("python environment: requirements.lock does not pin pytest", sha)

    root = repo_root.absolute()
    env_root = root / ".hotdocs" / "env"
    try:
        env_root.mkdir(parents=True, exist_ok=True)
        handle = open(env_root / "python.lock", "a")
    except OSError as exc:
        return _fail(f"python environment: {exc}", sha)
    try:
        if fcntl is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except OSError as exc:
                return _fail(f"python environment: {exc}", sha)

        env = env_root / "python"
        if os.name == "nt":
            interpreter = str(env / "Scripts" / "python.exe")
        else:
            interpreter = str(env / "bin" / "python")
        marker = f"{sha} {platform.python_version()}"
        marker_file = env / ".lock-sha256"

        ready = (
            os.path.isfile(interpreter)
            and os.access(interpreter, os.X_OK)
            and marker_file.is_file()
            and marker_file.read_text(encoding="utf-8") == marker
        )
        if not ready:
            reason = _run_tool("venv", [sys.executable, "-m", "venv", "--clear", str(env)])
            if reason is not None:
                return _fail(reason, sha)
            reason = _run_tool("pip", [
                interpreter, "-m", "pip", "install", "--no-input",
                "--disable-pip-version-check", "-r", str(lock),
            ])
            if reason is not None:
                return _fail(reason, sha)
            marker_file.write_text(marker, encoding="utf-8")

        return _versions(interpreter, sha)
    finally:
        handle.close()


def asset_runner(asset_file: Path):
    def run(entry: str, args: list):
        interpreter = _interpreter()
        try:
            proc = _run_code(
                asset_file, interpreter, _DRIVER,
                [_module_name(asset_file), entry, json.dumps(args)],
            )
        except subprocess.TimeoutExpired:
            raise AssetError("timed out after 30 seconds")
        except OSError:
            raise AssetError(f"cannot start {interpreter}")
        obj = _last_json(proc.stdout)
        if isinstance(obj, dict):
            if "v" in obj:
                return obj["v"]
            if "e" in obj:
                raise AssetError(obj["e"])
        raise AssetError(f"python exited {proc.returncode}: {_last_stderr_line(proc.stderr)}")

    return run


def _is_site(node):
    if isinstance(node, ast.Compare):
        return len(node.ops) == 1
    if isinstance(node, ast.BinOp):
        return type(node.op) in _SWAPS
    if isinstance(node, ast.Constant):
        return type(node.value) is bool
    return isinstance(node, ast.BoolOp)


def _mutate(node):
    if isinstance(node, ast.Compare):
        node.ops = [_SWAPS[type(node.ops[0])]()]
    elif isinstance(node, ast.BinOp):
        node.op = _SWAPS[type(node.op)]()
    elif isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    else:
        node.value = not node.value


def _parse_sites(asset_file, rel):
    tree = ast.parse((asset_file / rel).read_text(encoding="utf-8"))
    nodes = [node for node in list(ast.walk(tree)) if _is_site(node)]
    return tree, nodes


def _describe(rel, node):
    before = ast.unparse(node)
    _mutate(node)
    after = ast.unparse(node)
    _mutate(node)
    return f"{rel}:{node.lineno}: {before} -> {after}"


def strength_sites(asset_file: Path) -> list:
    sites = []
    for rel in _python_files(asset_file):
        _tree, nodes = _parse_sites(asset_file, rel)
        for index, node in enumerate(nodes):
            sites.append({"description": _describe(rel, node), "file": rel, "index": index})
    return sites


def apply_site(asset_file: Path, site: dict) -> None:
    rel = site["file"]
    tree, nodes = _parse_sites(asset_file, rel)
    index = site["index"]
    if index not in range(len(nodes)):
        raise ValueError(f"no site {index} in {rel}")
    node = nodes[index]
    if _describe(rel, node) != site["description"]:
        raise ValueError(f"site {index} of {rel} does not match")
    _mutate(node)
    (asset_file / rel).write_text(ast.unparse(tree), encoding="utf-8")


def guidance() -> dict:
    return {"generator": "", "test_author": ""}
