"""Surface checker: cheap rejection of a candidate that cannot work in place."""

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

_TIMEOUT = 60
_PROVISION_TIMEOUT = 600

_LOADER_RE = re.compile(r"importlib\.import_module\(|module_from_spec\(|exec_module\(|\b_load\w*\(")
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

_ADAPTER_SCRIPT = """
import importlib.util, json, sys
from pathlib import Path
path, func, arg = sys.argv[1], sys.argv[2], sys.argv[3]
name = Path(path).stem
spec = importlib.util.spec_from_file_location(name, path)
mod = importlib.util.module_from_spec(spec)
sys.modules[name] = mod
spec.loader.exec_module(mod)
r = getattr(mod, func)(Path(arg))
def get(k):
    return r.get(k) if isinstance(r, dict) else getattr(r, k, None)
if func == "surface":
    out = list(get("names"))
else:
    out = {"ok": get("ok"), "reason": get("reason"), "interpreter": get("interpreter")}
print(json.dumps(out))
"""

_DEP_SCRIPT = """
import importlib, json, sys
name = sys.argv[1]
mod = importlib.import_module(name)
missing = []
for n in json.loads(sys.argv[2]):
    if hasattr(mod, n):
        continue
    try:
        importlib.import_module(name + "." + n)
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


def _tool_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _run(cmd: list, pythonpath, timeout: int):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pythonpath)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        return subprocess.run(
            [str(c) for c in cmd],
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None


def _last_line(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _stdout_json(proc):
    return json.loads(_last_line(proc.stdout))


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


def _unquote(text: str) -> str:
    return text.strip().strip("'\"").strip()


def _inline_items(rest: str) -> list:
    inside = rest[rest.find("[") + 1:rest.rfind("]")]
    return [item.strip() for item in inside.split(",") if item.strip()]


def _depends_on(fm: list) -> list:
    for i, line in enumerate(fm):
        if line.startswith("depends_on:"):
            rest = line[len("depends_on:"):].strip()
            if rest.startswith("["):
                return [_unquote(item) for item in _inline_items(rest)]
            items = []
            for nxt in fm[i + 1:]:
                stripped = nxt.strip()
                if not stripped.startswith("-"):
                    break
                items.append(_unquote(stripped[1:]))
            return [item for item in items if item]
    return []


def _scalar(fm: list, key: str) -> str | None:
    for line in fm:
        if line.startswith(key + ":"):
            return _unquote(line[len(key) + 1:])
    return None


def _assets(fm: list) -> list:
    for line in fm:
        if line.startswith("assets:"):
            out = []
            for item in _inline_items(line):
                kind, _, path = item.partition(":")
                out.append((kind.strip(), path.strip()))
            return out
    return []


def _adapter_path(kind: str, repo_root: Path) -> Path | None:
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    candidate = repo_root / rel
    if candidate.is_file():
        return candidate
    tool = _tool_root()
    if tool is not None and (tool / rel).is_file():
        return tool / rel
    return None


def _call_adapter(adapter: Path, func: str, arg, timeout: int):
    """Returns (result, error); error is the last stderr line or 'timeout'."""
    proc = _run(
        [sys.executable, "-c", _ADAPTER_SCRIPT, adapter, func, arg],
        adapter.parent,
        timeout,
    )
    if proc is None:
        return None, "timeout"
    if proc.returncode != 0:
        return None, _last_line(proc.stderr)
    return _stdout_json(proc), None


def _environment(repo_root: Path):
    adapter = _adapter_path("python", repo_root)
    if adapter is None:
        return None, "unknown asset kind: python"
    result, error = _call_adapter(adapter, "provision", repo_root, _PROVISION_TIMEOUT)
    if error == "timeout":
        return None, "python environment: timed out"
    if error is not None:
        return None, f"python environment: {error}"
    if not result.get("ok"):
        return None, result.get("reason")
    return str(result.get("interpreter")), None


def _collect_uses(tree: ast.AST, src: str, deps: list) -> dict:
    result = {slug: set() for slug, _ in deps}
    scope_aliases: dict = {}

    def assign_scope(node, func):
        for child in ast.iter_child_nodes(node):
            inner = child if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else func
            if isinstance(child, (ast.Assign, ast.AnnAssign)) and child.value is not None:
                seg = ast.get_source_segment(src, child.value) or ""
                if _LOADER_RE.search(seg):
                    targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                    for slug, mod in deps:
                        quoted = (f'"{slug}"', f"'{slug}'", f'"{mod}"', f"'{mod}'")
                        if any(q in seg for q in quoted):
                            key = id(func) if func is not None else None
                            for target in targets:
                                if isinstance(target, ast.Name):
                                    scope_aliases.setdefault(key, {}).setdefault(target.id, set()).add(slug)
            assign_scope(child, inner)

    assign_scope(tree, None)

    def walk(node, stack):
        for child in ast.iter_child_nodes(node):
            st = stack
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                st = stack + [scope_aliases.get(id(child), {})]
            if (
                isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and not child.attr.startswith("__")
            ):
                name = child.value.id
                for slug, mod in deps:
                    if name == mod or any(slug in scope.get(name, ()) for scope in st):
                        result[slug].add(child.attr)
            walk(child, st)

    walk(tree, [scope_aliases.get(None, {})])
    return result


def _candidate_uses(code_dir: Path, deps: list) -> dict:
    uses = {slug: set() for slug, _ in deps}
    for path in sorted(code_dir.rglob("*.py")):
        if "__pycache__" in path.relative_to(code_dir).parts:
            continue
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue
        for slug, names in _collect_uses(tree, src, deps).items():
            uses[slug] |= names
    return uses


def _dep_dir(dep_slug: str, repo_root: Path) -> Path | None:
    fm = _frontmatter(repo_root / "specs" / "components" / dep_slug / "component.md")
    if _scalar(fm, "sealed") == "true":
        rel = Path(_scalar(fm, "source_path") or "")
    else:
        rel = Path("gen") / dep_slug
    if (repo_root / rel).is_dir():
        return repo_root / rel
    tool = _tool_root()
    if tool is not None and (tool / rel).is_dir():
        return tool / rel
    return None


def _dep_doc_text(dep_slug: str, repo_root: Path) -> str | None:
    rel = Path("specs") / "components" / dep_slug / "interface"
    roots = [repo_root]
    tool = _tool_root()
    if tool is not None:
        roots.append(tool)
    for root in roots:
        files = sorted((root / rel).rglob("*.md")) if (root / rel).is_dir() else []
        if files:
            return "\n".join(f.read_text(encoding="utf-8") for f in files)
    return None


def _dependency_findings(slug: str, repo_root: Path, code_dir: Path, interpreter: str) -> list:
    fm = _frontmatter(repo_root / "specs" / "components" / slug / "component.md")
    deps = []
    for dep_id in _depends_on(fm):
        dep_slug = _slug(dep_id)
        deps.append((dep_slug, dep_slug.replace("-", "_")))
    uses = _candidate_uses(code_dir, deps)
    findings = []
    for dep_slug, dep_module in deps:
        names = sorted(uses[dep_slug])
        if not names:
            continue
        dep_dir = _dep_dir(dep_slug, repo_root)
        if dep_dir is None:
            continue
        proc = _run(
            [interpreter, "-c", _DEP_SCRIPT, dep_module, json.dumps(names)],
            dep_dir,
            _TIMEOUT,
        )
        if proc is None or proc.returncode != 0:
            continue
        missing = set(_stdout_json(proc))
        doc = _dep_doc_text(dep_slug, repo_root)
        for name in names:
            if name in missing:
                findings.append({
                    "kind": "dependency_name",
                    "message": f"{dep_slug} has no {name}, which the candidate uses",
                })
            elif doc is not None and not re.search(r"\b" + re.escape(name) + r"\b", doc):
                findings.append({
                    "kind": "dependency_undocumented",
                    "message": f"{dep_slug} does not document {name}, which the candidate uses",
                })
    return findings


def _implements_cli(slug: str, repo_root: Path) -> bool:
    lib = repo_root / "specs" / "components" / slug / "interface" / "library.md"
    if not lib.is_file():
        return False
    for line in lib.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("Implements:") and "specs/architecture/cli-conventions.md" in stripped:
            return True
    return False


def _cli_finding(module: str, code_dir: Path, interpreter: str):
    proc = _run(
        [interpreter, "-c", f"import sys, {module}; sys.exit({module}.main(['--hotdocs-smoke-unknown']))"],
        code_dir,
        _TIMEOUT,
    )
    if proc is None:
        return {"kind": "cli_usage", "message": "timeout"}
    problems = []
    if proc.returncode != 2:
        problems.append(f"exit {proc.returncode}")
    lines = proc.stderr.splitlines()
    if not (lines and lines[0].startswith("usage error: ")):
        problems.append("no usage error line")
    if "Traceback" in proc.stderr:
        problems.append("traceback")
    if problems:
        return {"kind": "cli_usage", "message": ", ".join(problems)}
    return None


def _stated_names(text: str) -> list:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("```")), None)
    if start is None:
        return []
    block = []
    for line in lines[start + 1:]:
        if line.startswith("```"):
            break
        block.append(line)
    names = []
    for line in block:
        if not line.strip():
            continue
        head = line.split("(", 1)[0] if "(" in line else line
        idents = _IDENT_RE.findall(head)
        if idents:
            names.append(idents[-1])
    return names


def _asset_findings(slug: str, repo_root: Path, code_dir: Path) -> list:
    fm = _frontmatter(repo_root / "specs" / "components" / slug / "component.md")
    findings = []
    provisioned: dict = {}
    for kind, path in _assets(fm):
        adapter = _adapter_path(kind, repo_root)
        if adapter is None:
            findings.append({"kind": "asset_error", "message": f"unknown asset kind: {kind}"})
            continue
        if kind not in provisioned:
            result, error = _call_adapter(adapter, "provision", repo_root, _TIMEOUT)
            if error is not None:
                provisioned[kind] = error
            elif not result.get("ok"):
                provisioned[kind] = result.get("reason")
            else:
                provisioned[kind] = None
        if provisioned[kind] is not None:
            findings.append({"kind": "asset_error", "message": f"{path}: {provisioned[kind]}"})
            continue
        asset_file = code_dir / path
        if not asset_file.is_file():
            findings.append({"kind": "asset_error", "message": f"{path}: no such asset file"})
            continue
        file_name = path.rsplit("/", 1)[-1]
        iface = repo_root / "specs" / "components" / slug / "interface" / "assets" / f"{file_name}.md"
        if not iface.is_file():
            findings.append({
                "kind": "asset_error",
                "message": f"{path}: no interface file interface/assets/{file_name}.md",
            })
            continue
        names, error = _call_adapter(adapter, "surface", asset_file, _TIMEOUT)
        if error is not None:
            findings.append({"kind": "asset_error", "message": f"{path}: surface failed: {error}"})
            continue
        provided = set(names)
        for name in sorted(set(_stated_names(iface.read_text(encoding="utf-8")))):
            if name not in provided:
                findings.append({
                    "kind": "asset_name_missing",
                    "message": f"{path} has no {name}, which its interface states",
                })
    return findings


def _report(findings: list) -> SurfaceReport:
    return SurfaceReport(ok=not findings, findings=findings)


def check_surface(component_id: str, repo_root: Path, code_dir: Path | None = None) -> SurfaceReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    module = slug.replace("-", "_")
    code_dir = Path(code_dir) if code_dir is not None else repo_root / "gen" / slug

    interpreter, env_error = _environment(repo_root)
    if env_error is not None or interpreter is None:
        return _report([{"kind": "environment", "message": env_error}])

    proc = _run([interpreter, "-c", f"import {module}"], code_dir, _TIMEOUT)
    if proc is None:
        return _report([{"kind": "import_error", "message": "timeout"}])
    if proc.returncode != 0:
        return _report([{"kind": "import_error", "message": _last_line(proc.stderr)}])

    findings = _dependency_findings(slug, repo_root, code_dir, interpreter)

    if _implements_cli(slug, repo_root):
        cli = _cli_finding(module, code_dir, interpreter)
        if cli is not None:
            findings.append(cli)

    findings.extend(_asset_findings(slug, repo_root, code_dir))
    return _report(findings)
