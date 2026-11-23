"""Surface checker: rejects a candidate cheaply before the long verification.

Checks, in order: the ``python`` environment (R-SURF-006), an import of the
candidate (R-SURF-001), the names it uses on each direct dependency
(R-SURF-002), a smoke run of its command line (R-SURF-003) and the names each
declared asset provides (R-SURF-005).  The candidate only ever runs in a
subprocess.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "surface-checker@1.2.0"

_LOADER = re.compile(
    r"importlib\.import_module\(|module_from_spec\(|exec_module\(|\b_load\w*\("
)
_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_CLI_CONVENTIONS = "specs/architecture/cli-conventions.md"

_ADAPTER_SCRIPT = r"""
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location(sys.argv[1], sys.argv[2])
mod = importlib.util.module_from_spec(spec)
sys.modules[sys.argv[1]] = mod
spec.loader.exec_module(mod)
def get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)
if sys.argv[3] == "provision":
    r = mod.provision(Path(sys.argv[4]))
    print(json.dumps({"ok": bool(get(r, "ok")), "reason": get(r, "reason"),
                      "interpreter": get(r, "interpreter")}))
else:
    print(json.dumps(list(get(mod.surface(Path(sys.argv[4])), "names"))))
"""

_CHECK_NAMES = r"""
import importlib, json, sys
mod = importlib.import_module(sys.argv[1])
missing = []
for name in json.loads(sys.argv[2]):
    if hasattr(mod, name):
        continue
    try:
        importlib.import_module(sys.argv[1] + "." + name)
    except Exception:
        missing.append(name)
print(json.dumps(missing))
"""


@dataclass
class SurfaceReport:
    ok: bool
    findings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "findings": [dict(f) for f in self.findings]}


def _finding(kind: str, message: str) -> dict:
    return {"kind": kind, "message": message}


def _report(findings: list) -> SurfaceReport:
    return SurfaceReport(ok=not findings, findings=findings)


def _last(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _run(args: list, pythonpath: Path, timeout: int):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pythonpath)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [str(a) for a in args],
            cwd=str(pythonpath),
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "", "timeout"
    return proc.returncode, proc.stdout, proc.stderr


def _tool_root(default: Path) -> Path:
    return next(
        (p.parent for p in Path(__file__).resolve().parents if p.name == "gen"),
        default,
    )


def _adapter(kind: str, repo_root: Path):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    for root in (repo_root, _tool_root(repo_root)):
        if (root / rel).is_file():
            return root / rel
    return None


def _call_adapter(adapter: Path, mode: str, arg, timeout: int):
    return _run(
        [sys.executable, "-c", _ADAPTER_SCRIPT, adapter.stem, adapter, mode, arg],
        adapter.parent,
        timeout,
    )


def _provision(adapter: Path, repo_root: Path, timeout: int):
    rc, out, err = _call_adapter(adapter, "provision", repo_root, timeout)
    if rc != 0:
        return None, ("timed out" if rc is None else _last(err))
    return json.loads(_last(out)), None


def _read(path: Path) -> str:
    return path.read_text(errors="replace") if path.is_file() else ""


def _frontmatter(path: Path) -> list:
    lines = _read(path).splitlines()
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def _scalar(fm: list, key: str) -> str:
    for line in fm:
        if line.startswith(key + ":"):
            return line[len(key) + 1:].strip().strip("'\"")
    return ""


def _list(fm: list, key: str) -> list:
    for i, line in enumerate(fm):
        if line.startswith(key + ":"):
            rest = line[len(key) + 1:].strip()
            if rest.startswith("["):
                inner = rest[1:rest.rfind("]")]
                return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
            items = []
            for item in fm[i + 1:]:
                stripped = item.strip()
                if not stripped.startswith("-"):
                    break
                items.append(stripped[1:].strip().strip("'\""))
            return items
    return []


def _assets(fm: list) -> list:
    for line in fm:
        if line.startswith("assets:"):
            inner = line[line.find("[") + 1:line.rfind("]")]
            items = [item.strip() for item in inner.split(",") if item.strip()]
            return [tuple(part.strip() for part in item.split(":", 1)) for item in items]
    return []


def _uses(src: str, dep_slug: str, dep_module: str) -> set:
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return set()
    quoted = re.compile(
        r"""(['"])(%s|%s)\1""" % (re.escape(dep_slug), re.escape(dep_module))
    )
    aliases = {dep_module}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            right = ast.get_source_segment(src, node.value) or ""
            if _LOADER.search(right) and quoted.search(right):
                aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in aliases
        and not node.attr.startswith("__")
    }


def _stated(text: str) -> set:
    lines = text.splitlines()
    fences = [i for i, line in enumerate(lines) if line.startswith("```")]
    start, end = (fences + [len(lines), len(lines)])[:2]
    names = set()
    for line in lines[start + 1:end]:
        ids = _IDENT.findall(line.split("(", 1)[0])
        if ids:
            names.add(ids[-1])
    return names


def _check_asset(kind, path, repo_root, code_dir, iface_dir, provisioned) -> list:
    adapter = _adapter(kind, repo_root)
    if adapter is None:
        return [_finding("asset_error", f"unknown asset kind: {kind}")]
    if kind not in provisioned:
        provisioned[kind] = _provision(adapter, repo_root, 60)
    result, err = provisioned[kind]
    if result is None or not result["ok"]:
        reason = err if result is None else result["reason"]
        return [_finding("asset_error", f"{path}: {reason}")]
    asset_file = code_dir / path
    if not asset_file.is_file():
        return [_finding("asset_error", f"{path}: no such asset file")]
    file_name = path.rsplit("/", 1)[-1]
    iface = iface_dir / "assets" / f"{file_name}.md"
    if not iface.is_file():
        return [_finding(
            "asset_error",
            f"{path}: no interface file interface/assets/{file_name}.md",
        )]
    rc, out, err = _call_adapter(adapter, "surface", asset_file, 60)
    if rc != 0:
        return [_finding("asset_error", f"{path}: surface failed: {_last(err)}")]
    provided = set(json.loads(_last(out)))
    return [
        _finding("asset_name_missing", f"{path} has no {name}, which its interface states")
        for name in sorted(_stated(iface.read_text(errors="replace")) - provided)
    ]


def check_surface(component_id: str, repo_root: Path, code_dir: Path | None = None) -> SurfaceReport:
    repo_root = Path(repo_root).absolute()
    slug = component_id.removeprefix("comp-")
    module = slug.replace("-", "_")
    code_dir = Path(code_dir).absolute() if code_dir is not None else repo_root / "gen" / slug

    # R-SURF-006: environment.
    adapter = _adapter("python", repo_root)
    if adapter is None:
        return _report([_finding("environment", "unknown asset kind: python")])
    env, err = _provision(adapter, repo_root, 600)
    if env is None:
        return _report([_finding("environment", f"python environment: {err}")])
    if not env["ok"]:
        return _report([_finding("environment", env["reason"])])
    interpreter = env["interpreter"]

    # R-SURF-001: import.
    rc, _, err = _run([interpreter, "-c", f"import {module}"], code_dir, 60)
    if rc != 0:
        return _report([_finding("import_error", _last(err))])

    findings = []
    spec_dir = repo_root / "specs" / "components"
    fm = _frontmatter(spec_dir / slug / "component.md")

    # R-SURF-002: dependency names.
    sources = [
        p.read_text(errors="replace")
        for p in sorted(code_dir.rglob("*.py"))
        if "__pycache__" not in p.relative_to(code_dir).parts
    ]
    for dep in _list(fm, "depends_on"):
        dep_slug = dep.removeprefix("comp-")
        dep_module = dep_slug.replace("-", "_")
        dep_fm = _frontmatter(spec_dir / dep_slug / "component.md")
        if _scalar(dep_fm, "sealed") == "true":
            dep_dir = repo_root / _scalar(dep_fm, "source_path")
        else:
            dep_dir = repo_root / "gen" / dep_slug
        if not dep_dir.is_dir():
            continue
        names = sorted(set().union(*(_uses(src, dep_slug, dep_module) for src in sources)))
        rc, out, _ = _run(
            [interpreter, "-c", _CHECK_NAMES, dep_module, json.dumps(names)], dep_dir, 60
        )
        if rc != 0:
            continue
        for name in json.loads(_last(out)):
            findings.append(_finding(
                "dependency_name", f"{dep_slug} has no {name}, which the candidate uses"
            ))

    # R-SURF-003: command line.
    iface_dir = spec_dir / slug / "interface"
    library = _read(iface_dir / "library.md").splitlines()
    if any(line.startswith("Implements:") and _CLI_CONVENTIONS in line for line in library):
        code = f"import sys, {module}; sys.exit({module}.main(['--hotdocs-smoke-unknown']))"
        rc, _, err = _run([interpreter, "-c", code], code_dir, 60)
        if rc is None:
            findings.append(_finding("cli_usage", "timeout"))
        else:
            parts = []
            if rc != 2:
                parts.append(f"exit {rc}")
            if not (err.splitlines() or [""])[0].startswith("usage error: "):
                parts.append("no usage error line")
            if "Traceback" in err:
                parts.append("traceback")
            if parts:
                findings.append(_finding("cli_usage", ", ".join(parts)))

    # R-SURF-005: assets.
    provisioned: dict = {}
    for kind, path in _assets(fm):
        findings.extend(_check_asset(kind, path, repo_root, code_dir, iface_dir, provisioned))

    return _report(findings)
