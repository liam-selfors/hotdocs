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
    """A failure of the code or of its process."""


_SURFACE_PROGRAM = "\n".join([
    r"import importlib,json,sys",
    r"print('\n'+json.dumps(sorted(n for n in dir(importlib.import_module(sys.argv[1])) if not n.startswith('_'))))",
])

_VERSIONS_PROGRAM = "\n".join([
    r"import hashlib,json,platform,re",
    r"from importlib.metadata import distributions as ds",
    r"s=sorted({re.sub(r'[-_.]+','-',str(d.metadata['Name']).lower())+'=='+str(d.version) for d in ds()})",
    r"print(json.dumps({'python':platform.python_version(),'packages':'sha256:'+hashlib.sha256('\n'.join(s).encode()).hexdigest()}))",
])

_DRIVER = "\n".join([
    r"import importlib,json,sys",
    r"m,e,a=sys.argv[1:4]",
    r"try:",
    r" f=getattr(importlib.import_module(m),e,None)",
    r" o=json.dumps({'v':f(*json.loads(a))} if callable(f) else {'e':'no entry '+e})",
    r"except BaseException as x:",
    r" o=json.dumps({'e':str(x)})",
    r"print('\n'+o)",
])

_CMP_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}

_BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}

_BIN_SWAP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod, ast.Mod: ast.FloorDiv,
}

_PIN_SPLIT = re.compile(r"[=<>!~\[;@ ]")


# ---------------------------------------------------------------- helpers

def _python_files(asset_file):
    found = []
    for path in Path(asset_file).rglob("*.py"):
        rel = path.relative_to(asset_file)
        if "__pycache__" in rel.parts or not path.is_file():
            continue
        found.append((rel.as_posix(), path))
    found.sort(key=lambda item: item[0])
    return found


def _module_name(asset_file):
    return Path(asset_file).name.replace("-", "_")


def _interpreter():
    return os.environ.get("HOTDOCS_PYTHON") or sys.executable


def _last_line(text):
    lines = [line for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else None


def _decode_last(text):
    line = _last_line(text)
    if line is None:
        return None
    try:
        return json.loads(line)
    except ValueError:
        return None


def _run_in_code_dir(asset_file, interpreter, args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(asset_file)
    return subprocess.run(
        [interpreter] + args,
        cwd=str(asset_file),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------- layout

def layout_errors(asset_file):
    errors = []
    for rel, path in _python_files(asset_file):
        try:
            ast.parse(path.read_bytes())
        except SyntaxError as exc:
            errors.append(f"{rel}:{exc.lineno or 0}: SyntaxError: {exc.msg}")
        except ValueError as exc:
            errors.append(f"{rel}:0: SyntaxError: {exc}")
    return errors


# ---------------------------------------------------------------- surface

def surface(asset_file):
    try:
        proc = _run_in_code_dir(
            asset_file, _interpreter(),
            ["-c", _SURFACE_PROGRAM, _module_name(asset_file)],
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"names": []}
    if proc.returncode != 0:
        return {"names": []}
    names = _decode_last(proc.stdout)
    if not isinstance(names, list):
        return {"names": []}
    return {"names": names}


# ---------------------------------------------------------------- provision

def _result(ok, reason, versions, lockfile_sha256, interpreter):
    return {
        "ok": ok,
        "reason": reason,
        "versions": versions,
        "lockfile_sha256": lockfile_sha256,
        "interpreter": interpreter,
    }


def _fail(reason, lockfile_sha256):
    return _result(False, f"python environment: {reason}", {}, lockfile_sha256, None)


def _pins_pytest(text):
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = _PIN_SPLIT.split(line, 1)[0]
        if re.sub(r"[-_.]+", "-", name.lower()) == "pytest":
            return True
    return False


def _versions(interpreter, lockfile_sha256):
    try:
        proc = subprocess.run(
            [interpreter, "-I", "-c", _VERSIONS_PROGRAM],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _fail("python version check failed", lockfile_sha256)
    versions = _decode_last(proc.stdout) if proc.returncode == 0 else None
    if not isinstance(versions, dict):
        return _fail("python version check failed", lockfile_sha256)
    return _result(True, "", versions, lockfile_sha256, interpreter)


def _command(argv, program):
    """Run a build command; return a failure reason or None."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return f"{program} timed out"
    if proc.returncode != 0:
        line = _last_line(proc.stderr)
        if line is None:
            return f"{program} exited {proc.returncode}"
        return line.strip()
    return None


def _build_env(envroot, lock, lockfile_sha256):
    env = envroot / "python"
    if os.name == "nt":
        interpreter = str(env / "Scripts" / "python.exe")
    else:
        interpreter = str(env / "bin" / "python")
    marker_text = f"{lockfile_sha256} {platform.python_version()}"
    marker = env / ".lock-sha256"
    ready = (
        os.path.isfile(interpreter)
        and os.access(interpreter, os.X_OK)
        and marker.is_file()
        and marker.read_text(encoding="utf-8") == marker_text
    )
    if not ready:
        reason = _command(
            [sys.executable, "-m", "venv", "--clear", str(env)], "venv")
        if reason is not None:
            return _fail(reason, lockfile_sha256)
        reason = _command(
            [interpreter, "-m", "pip", "install", "--no-input",
             "--disable-pip-version-check", "-r", str(lock)], "pip")
        if reason is not None:
            return _fail(reason, lockfile_sha256)
        marker.write_text(marker_text, encoding="utf-8")
    return _versions(interpreter, lockfile_sha256)


def provision(repo_root):
    repo_root = Path(repo_root)
    envdir = repo_root / "environments" / "python"
    lock = envdir / "requirements.lock"
    lock_bytes = lock.read_bytes() if lock.is_file() else None
    lockfile_sha256 = None
    if lock_bytes is not None:
        lockfile_sha256 = "sha256:" + hashlib.sha256(lock_bytes).hexdigest()

    pin_file = envdir / "python-version"
    if pin_file.is_file():
        pin = pin_file.read_text(encoding="utf-8").strip()
        version = platform.python_version()
        if pin and not (version == pin or version.startswith(pin + ".")):
            return _fail(f"needs Python {pin}, found {version}", lockfile_sha256)

    if lock_bytes is None:
        return _versions(sys.executable, None)

    if not _pins_pytest(lock_bytes.decode("utf-8")):
        return _fail("requirements.lock does not pin pytest", lockfile_sha256)

    root = repo_root.absolute()
    envroot = root / ".hotdocs" / "env"
    handle = None
    try:
        envroot.mkdir(parents=True, exist_ok=True)
        handle = open(envroot / "python.lock", "a")
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except OSError as exc:
        if handle is not None:
            handle.close()
        return _fail(str(exc), lockfile_sha256)
    try:
        return _build_env(envroot, lock, lockfile_sha256)
    finally:
        handle.close()


# ---------------------------------------------------------------- runner

def asset_runner(asset_file):
    module = _module_name(asset_file)

    def run(entry, args):
        interpreter = _interpreter()
        try:
            proc = _run_in_code_dir(
                asset_file, interpreter,
                ["-c", _DRIVER, module, entry, json.dumps(args)],
            )
        except OSError:
            raise AssetError(f"cannot start {interpreter}")
        except subprocess.TimeoutExpired:
            raise AssetError("timed out after 30 seconds")
        obj = _decode_last(proc.stdout)
        if isinstance(obj, dict):
            if "v" in obj:
                return obj["v"]
            raise AssetError(obj["e"])
        line = _last_line(proc.stderr)
        detail = line.strip() if line is not None else ""
        raise AssetError(f"python exited {proc.returncode}: {detail}")

    return run


# ---------------------------------------------------------------- strength

def _is_site(node):
    if isinstance(node, ast.Compare):
        return len(node.ops) == 1 and type(node.ops[0]) in _CMP_SWAP
    if isinstance(node, ast.BoolOp):
        return True
    if isinstance(node, ast.BinOp):
        return type(node.op) in _BIN_SWAP
    if isinstance(node, ast.Constant):
        return isinstance(node.value, bool)
    return False


def _flip(node):
    """Apply a site's change; applying it again undoes it."""
    if isinstance(node, ast.Compare):
        node.ops[0] = _CMP_SWAP[type(node.ops[0])]()
    elif isinstance(node, ast.BoolOp):
        node.op = _BOOL_SWAP[type(node.op)]()
    elif isinstance(node, ast.BinOp):
        node.op = _BIN_SWAP[type(node.op)]()
    else:
        node.value = not node.value


def _describe(rel, node):
    before = ast.unparse(node)
    _flip(node)
    after = ast.unparse(node)
    _flip(node)
    return f"{rel}:{node.lineno}: {before} -> {after}"


def _sites(tree):
    return [node for node in ast.walk(tree) if _is_site(node)]


def strength_sites(asset_file):
    result = []
    for rel, path in _python_files(asset_file):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for index, node in enumerate(_sites(tree)):
            result.append({
                "description": _describe(rel, node),
                "file": rel,
                "index": index,
            })
    return result


def apply_site(asset_file, site):
    rel = site["file"]
    path = Path(asset_file) / rel
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = _sites(tree)
    index = site["index"]
    if not (0 <= index < len(nodes)):
        raise ValueError(f"no site {index} in {rel}")
    node = nodes[index]
    if _describe(rel, node) != site["description"]:
        raise ValueError(f"site {index} of {rel} does not match its description")
    _flip(node)
    path.write_text(ast.unparse(tree), encoding="utf-8")


# ---------------------------------------------------------------- guidance

def guidance():
    return {"generator": "", "test_author": ""}
