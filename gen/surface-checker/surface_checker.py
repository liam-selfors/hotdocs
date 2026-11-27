"""Surface checker: rejects a candidate cheaply before the long verification."""

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

_CHECK_TIMEOUT = 60
_PROVISION_TIMEOUT = 600
_CLI_CONVENTIONS = "specs/architecture/cli-conventions.md"
_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

_ADAPTER_SCRIPT = r"""
import sys, json, importlib.util
from pathlib import Path
name, path, func, arg = sys.argv[1:5]
spec = importlib.util.spec_from_file_location(name, path)
mod = importlib.util.module_from_spec(spec)
sys.modules[name] = mod
spec.loader.exec_module(mod)
r = getattr(mod, func)(Path(arg))
def g(o, k):
    return o.get(k) if isinstance(o, dict) else getattr(o, k, None)
if func == "surface":
    out = g(r, "names")
else:
    out = {k: g(r, k) for k in ("ok", "reason", "versions", "lockfile_sha256", "interpreter")}
print(json.dumps(out))
"""

_DEP_SCRIPT = r"""
import sys, json, importlib
mod_name = sys.argv[1]
names = json.loads(sys.argv[2])
try:
    m = importlib.import_module(mod_name)
except BaseException:
    sys.exit(3)
missing = []
for n in names:
    if hasattr(m, n):
        continue
    try:
        importlib.import_module(mod_name + "." + n)
    except BaseException:
        missing.append(n)
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


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _run(cmd: list, pythonpath: Path, timeout: int):
    """Run cmd; return CompletedProcess, or None on timeout."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pythonpath)
    try:
        return subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _find_adapter(kind: str, repo_root: Path):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    for root in (repo_root, _tool_root()):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def _call_adapter(adapter: Path, func: str, arg: Path, timeout: int):
    """Return (value, error); error is "timeout" or the last stderr line."""
    name = adapter.stem
    proc = _run(
        [sys.executable, "-c", _ADAPTER_SCRIPT, name, str(adapter), func, str(arg)],
        adapter.parent,
        timeout,
    )
    if proc is None:
        return None, "timeout"
    if proc.returncode != 0:
        return None, _last_line(proc.stderr)
    return json.loads(_last_line(proc.stdout)), None


def _frontmatter(path: Path) -> list:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def _inline_list(lines: list, key: str) -> list:
    for line in lines:
        if line.startswith(f"{key}:"):
            start = line.find("[")
            end = line.find("]", start + 1)
            if start < 0 or end < 0:
                return []
            items = [i.strip().strip("'\"") for i in line[start + 1:end].split(",")]
            return [i for i in items if i]
    return []


def _scalar(lines: list, key: str):
    for line in lines:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return None


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _call_name(func) -> tuple:
    if isinstance(func, ast.Attribute):
        owner = func.value.id if isinstance(func.value, ast.Name) else None
        return owner, func.attr
    if isinstance(func, ast.Name):
        return None, func.id
    return None, None


def _is_loader_call(node: ast.Call) -> bool:
    owner, name = _call_name(node.func)
    if name is None:
        return False
    if name == "import_module" and owner == "importlib":
        return True
    return name in ("module_from_spec", "exec_module") or name.startswith("_load")


def _aliases(tree: ast.AST, dep_slug: str, dep_module: str) -> set:
    aliases = {dep_module}
    wanted = {dep_slug, dep_module}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        sub = list(ast.walk(value))
        calls = any(isinstance(n, ast.Call) and _is_loader_call(n) for n in sub)
        quoted = any(isinstance(n, ast.Constant) and n.value in wanted for n in sub)
        if calls and quoted:
            aliases.update(t.id for t in targets if isinstance(t, ast.Name))
    return aliases


def _uses(code_dir: Path, dep_slug: str, dep_module: str) -> list:
    names = set()
    for path in sorted(code_dir.rglob("*.py")):
        if "__pycache__" in path.relative_to(code_dir).parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        aliases = _aliases(tree, dep_slug, dep_module)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and not node.attr.startswith("__")
            ):
                names.add(node.attr)
    return sorted(names)


def _dependency_dir(repo_root: Path, dep_slug: str) -> Path:
    fm = _frontmatter(repo_root / "specs" / "components" / dep_slug / "component.md")
    if _scalar(fm, "sealed") == "true":
        return repo_root / _scalar(fm, "source_path")
    return repo_root / "gen" / dep_slug


def _check_dependencies(interp, repo_root, code_dir, depends_on) -> list:
    findings = []
    for dep_id in depends_on:
        dep_slug = _slug(dep_id)
        dep_module = dep_slug.replace("-", "_")
        dep_dir = _dependency_dir(repo_root, dep_slug)
        if not dep_dir.is_dir():
            continue
        names = _uses(code_dir, dep_slug, dep_module)
        proc = _run(
            [interp, "-c", _DEP_SCRIPT, dep_module, json.dumps(names)],
            dep_dir,
            _CHECK_TIMEOUT,
        )
        if proc is None or proc.returncode != 0:
            continue
        for name in sorted(json.loads(_last_line(proc.stdout))):
            findings.append(
                _finding("dependency_name", f"{dep_slug} has no {name}, which the candidate uses")
            )
    return findings


def _implements_cli(spec_dir: Path) -> bool:
    library = spec_dir / "interface" / "library.md"
    if not library.is_file():
        return False
    return any(
        line.startswith("Implements:") and _CLI_CONVENTIONS in line
        for line in library.read_text(encoding="utf-8").splitlines()
    )


def _check_cli(interp, code_dir, module) -> list:
    code = f"import sys, {module}; sys.exit({module}.main(['--hotdocs-smoke-unknown']))"
    proc = _run([interp, "-c", code], code_dir, _CHECK_TIMEOUT)
    if proc is None:
        return [_finding("cli_usage", "timeout")]
    differed = []
    if proc.returncode != 2:
        differed.append(f"exit {proc.returncode}")
    lines = proc.stderr.splitlines()
    if not (lines and lines[0].startswith("usage error: ")):
        differed.append("no usage error line")
    if "Traceback" in proc.stderr:
        differed.append("traceback")
    if differed:
        return [_finding("cli_usage", ", ".join(differed))]
    return []


def _stated_names(interface_file: Path) -> list:
    lines = interface_file.read_text(encoding="utf-8").splitlines()
    block = []
    inside = False
    for line in lines:
        if line.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside:
            block.append(line)
    names = []
    for line in block:
        if not line.strip():
            continue
        head = line[: line.index("(")] if "(" in line else line
        idents = _IDENT.findall(head)
        if idents:
            names.append(idents[-1])
    return names


def _check_assets(repo_root, code_dir, spec_dir, assets) -> list:
    findings = []
    provisioned = {}
    for kind, path in assets:
        adapter = _find_adapter(kind, repo_root)
        if adapter is None:
            findings.append(_finding("asset_error", f"unknown asset kind: {kind}"))
            continue
        if kind not in provisioned:
            provisioned[kind] = _call_adapter(adapter, "provision", repo_root, _CHECK_TIMEOUT)
        result, error = provisioned[kind]
        if error is not None:
            findings.append(_finding("asset_error", f"{path}: {error}"))
            continue
        if not result.get("ok"):
            findings.append(_finding("asset_error", f"{path}: {result.get('reason')}"))
            continue
        asset_file = code_dir / path
        if not asset_file.is_file():
            findings.append(_finding("asset_error", f"{path}: no such asset file"))
            continue
        file_name = path.rsplit("/", 1)[-1]
        interface_file = spec_dir / "interface" / "assets" / f"{file_name}.md"
        if not interface_file.is_file():
            findings.append(
                _finding(
                    "asset_error",
                    f"{path}: no interface file interface/assets/{file_name}.md",
                )
            )
            continue
        provided, error = _call_adapter(adapter, "surface", asset_file, _CHECK_TIMEOUT)
        if error is not None:
            findings.append(_finding("asset_error", f"{path}: surface failed: {error}"))
            continue
        for name in sorted(set(_stated_names(interface_file)) - set(provided)):
            findings.append(
                _finding("asset_name_missing", f"{path} has no {name}, which its interface states")
            )
    return findings


def _parse_assets(fm: list) -> list:
    out = []
    for item in _inline_list(fm, "assets"):
        kind, _, path = item.partition(":")
        out.append((kind.strip(), path.strip()))
    return out


def _check_environment(repo_root: Path):
    """Return (interpreter, findings)."""
    adapter = _find_adapter("python", repo_root)
    if adapter is None:
        return None, [_finding("environment", "unknown asset kind: python")]
    result, error = _call_adapter(adapter, "provision", repo_root, _PROVISION_TIMEOUT)
    if error == "timeout":
        return None, [_finding("environment", "python environment: timed out")]
    if error is not None:
        return None, [_finding("environment", f"python environment: {error}")]
    if not result.get("ok"):
        return None, [_finding("environment", result.get("reason"))]
    return result.get("interpreter"), []


def check_surface(component_id: str, repo_root: Path, code_dir: Path | None = None) -> SurfaceReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    module = slug.replace("-", "_")
    code_dir = Path(code_dir) if code_dir is not None else repo_root / "gen" / slug
    spec_dir = repo_root / "specs" / "components" / slug

    interp, findings = _check_environment(repo_root)
    if findings:
        return SurfaceReport(ok=False, findings=findings)

    proc = _run([interp, "-c", f"import {module}"], code_dir, _CHECK_TIMEOUT)
    if proc is None:
        return SurfaceReport(ok=False, findings=[_finding("import_error", "timeout")])
    if proc.returncode != 0:
        return SurfaceReport(
            ok=False, findings=[_finding("import_error", _last_line(proc.stderr))]
        )

    fm = _frontmatter(spec_dir / "component.md")
    findings.extend(
        _check_dependencies(interp, repo_root, code_dir, _inline_list(fm, "depends_on"))
    )
    if _implements_cli(spec_dir):
        findings.extend(_check_cli(interp, code_dir, module))
    findings.extend(_check_assets(repo_root, code_dir, spec_dir, _parse_assets(fm)))
    return SurfaceReport(ok=not findings, findings=findings)
