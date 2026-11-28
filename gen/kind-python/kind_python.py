"""Adapter for the ``python`` asset kind."""

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
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None

KIND = "python"
GATE_VERSION = "kind-python@1.0.0"


class AssetError(Exception):
    """A failure of the asset's code or of its process."""


_SURFACE_PROGRAM = r"""import importlib,json,sys
print('\n'+json.dumps(sorted(n for n in dir(importlib.import_module(sys.argv[1])) if not n.startswith('_'))))"""

_DRIVER_PROGRAM = r"""import importlib,json,sys
m,e,a=sys.argv[1:4]
try:
 f=getattr(importlib.import_module(m),e,None)
 o=json.dumps({'v':f(*json.loads(a))} if callable(f) else {'e':'no entry '+e})
except BaseException as x:
 o=json.dumps({'e':str(x)})
print('\n'+o)"""

_VERSIONS_PROGRAM = r"""import hashlib,json,platform,re
from importlib.metadata import distributions as ds
s=sorted({re.sub(r'[-_.]+','-',str(d.metadata['Name']).lower())+'=='+str(d.version) for d in ds()})
print(json.dumps({'python':platform.python_version(),'packages':'sha256:'+hashlib.sha256('\n'.join(s).encode()).hexdigest()}))"""


# ---------------------------------------------------------------- helpers


def _python_files(asset_file):
    found = []
    for path in asset_file.rglob("*.py"):
        rel = path.relative_to(asset_file)
        if "__pycache__" in rel.parts or not path.is_file():
            continue
        found.append((rel.as_posix(), path))
    found.sort(key=lambda item: item[0])
    return found


def _module_name(asset_file):
    return asset_file.name.replace("-", "_")


def _interpreter():
    return os.environ.get("HOTDOCS_PYTHON") or sys.executable


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


def _last_line(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _decode_last(text):
    try:
        return json.loads(_last_line(text))
    except ValueError:
        return None


# ---------------------------------------------------------------- layout


def layout_errors(asset_file):
    errors = []
    for rel, path in _python_files(asset_file):
        try:
            ast.parse(path.read_bytes())
        except SyntaxError as exc:
            errors.append(f"{rel}:{exc.lineno or 0}: SyntaxError: {exc.msg}")
        except ValueError as exc:
            errors.append(
                f"{rel}:{getattr(exc, 'lineno', None) or 0}: SyntaxError: {exc}"
            )
    return errors


# ---------------------------------------------------------------- surface


def surface(asset_file):
    try:
        proc = _run_in_code_dir(
            asset_file,
            _interpreter(),
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
    return _result(False, "python environment: " + reason, {}, lockfile_sha256, None)


def _versions(interpreter):
    try:
        proc = subprocess.run(
            [interpreter, "-I", "-c", _VERSIONS_PROGRAM],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    obj = _decode_last(proc.stdout)
    if not isinstance(obj, dict):
        return None
    return obj


def _pins_pytest(text):
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("-"):
            continue
        name = re.split(r"[=<>!~\[;@ ]", s, maxsplit=1)[0]
        if re.sub(r"[-_.]+", "-", name.lower()) == "pytest":
            return True
    return False


def _command(program, args):
    """Run venv or pip; return an error reason, or None on success."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return f"{program} timed out"
    if proc.returncode != 0:
        return _last_line(proc.stderr) or f"{program} exited {proc.returncode}"
    return None


def _finish(interpreter, lockfile_sha256):
    versions = _versions(interpreter)
    if versions is None:
        return _fail("python version check failed", lockfile_sha256)
    return _result(True, "", versions, lockfile_sha256, interpreter)


def provision(repo_root):
    env_dir = repo_root / "environments" / "python"
    lock = env_dir / "requirements.lock"
    has_lock = lock.is_file()
    lockfile_sha256 = (
        "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest() if has_lock else None
    )

    pin_file = env_dir / "python-version"
    if pin_file.is_file():
        pin = pin_file.read_text(encoding="utf-8").strip()
        version = platform.python_version()
        if pin and not (version == pin or version.startswith(pin + ".")):
            return _fail(f"needs Python {pin}, found {version}", lockfile_sha256)

    if not has_lock:
        return _finish(sys.executable, None)

    if not _pins_pytest(lock.read_text(encoding="utf-8")):
        return _fail("requirements.lock does not pin pytest", lockfile_sha256)

    root = repo_root.absolute()
    env_root = root / ".hotdocs" / "env"
    try:
        env_root.mkdir(parents=True, exist_ok=True)
        handle = open(env_root / "python.lock", "a")
    except OSError as exc:
        return _fail(str(exc), lockfile_sha256)
    try:
        if fcntl is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX)
            except OSError as exc:
                return _fail(str(exc), lockfile_sha256)
        return _build(env_root / "python", lock, lockfile_sha256)
    finally:
        handle.close()


def _build(env, lock, lockfile_sha256):
    if os.name == "nt":
        interpreter = str(env / "Scripts" / "python.exe")
    else:
        interpreter = str(env / "bin" / "python")
    marker_text = f"{lockfile_sha256} {platform.python_version()}"
    marker = env / ".lock-sha256"

    executable = os.path.isfile(interpreter) and os.access(interpreter, os.X_OK)
    current = marker.is_file() and marker.read_text(encoding="utf-8") == marker_text
    if not (executable and current):
        error = _command("venv", [sys.executable, "-m", "venv", "--clear", str(env)])
        if error is None:
            error = _command(
                "pip",
                [
                    interpreter,
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "--disable-pip-version-check",
                    "-r",
                    str(lock),
                ],
            )
        if error is not None:
            return _fail(error, lockfile_sha256)
        marker.write_text(marker_text, encoding="utf-8")

    return _finish(interpreter, lockfile_sha256)


# ---------------------------------------------------------------- runner


def asset_runner(asset_file):
    def run(entry, args):
        interpreter = _interpreter()
        try:
            proc = _run_in_code_dir(
                asset_file,
                interpreter,
                ["-c", _DRIVER_PROGRAM, _module_name(asset_file), entry, json.dumps(args)],
            )
        except OSError:
            raise AssetError(f"cannot start {interpreter}")
        except subprocess.TimeoutExpired:
            raise AssetError("timed out after 30 seconds")
        obj = _decode_last(proc.stdout)
        if isinstance(obj, dict) and "v" in obj:
            return obj["v"]
        if isinstance(obj, dict) and "e" in obj:
            raise AssetError(obj["e"])
        raise AssetError(
            f"python exited {proc.returncode}: {_last_line(proc.stderr)}"
        )

    return run


# ---------------------------------------------------------------- strength

_COMPARE_SWAPS = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}

_BINOP_SWAPS = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod,
    ast.Mod: ast.FloorDiv,
}


def _is_site(node):
    if isinstance(node, ast.Compare):
        return len(node.ops) == 1
    if isinstance(node, ast.BoolOp):
        return True
    if isinstance(node, ast.BinOp):
        return type(node.op) in _BINOP_SWAPS
    if isinstance(node, ast.Constant):
        return isinstance(node.value, bool)
    return False


def _flip(node):
    """Apply a site's change; applying it twice restores the node."""
    if isinstance(node, ast.Compare):
        node.ops[0] = _COMPARE_SWAPS[type(node.ops[0])]()
    elif isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif isinstance(node, ast.BinOp):
        node.op = _BINOP_SWAPS[type(node.op)]()
    else:
        node.value = not node.value


def _site_nodes(tree):
    return [node for node in ast.walk(tree) if _is_site(node)]


def _describe(rel, node):
    before = ast.unparse(node)
    _flip(node)
    after = ast.unparse(node)
    return f"{rel}:{node.lineno}: {before} -> {after}"


def strength_sites(asset_file):
    sites = []
    for rel, path in _python_files(asset_file):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for index, node in enumerate(_site_nodes(tree)):
            description = _describe(rel, node)
            _flip(node)
            sites.append({"description": description, "file": rel, "index": index})
    return sites


def apply_site(asset_file, site):
    path = asset_file / site["file"]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = _site_nodes(tree)
    index = site["index"]
    if not 0 <= index < len(nodes):
        raise ValueError(f"no site {index} in {site['file']}")
    if _describe(site["file"], nodes[index]) != site["description"]:
        raise ValueError(f"site {index} of {site['file']} does not match")
    path.write_text(ast.unparse(tree), encoding="utf-8")


# ---------------------------------------------------------------- guidance


def guidance():
    return {"generator": "", "test_author": ""}
