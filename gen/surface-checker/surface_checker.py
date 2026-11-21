"""Surface checker: cheap pre-verification rejection of a generated candidate."""

from __future__ import annotations

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
_CLI_CONVENTIONS = "specs/architecture/cli-conventions.md"
_SMOKE_ARG = "--hotdocs-smoke-unknown"

_ADAPTER_SCRIPT = r"""
import importlib.util, json, sys
from pathlib import Path
path, func, arg = sys.argv[1:4]
name = Path(path).stem
spec = importlib.util.spec_from_file_location(name, path)
mod = importlib.util.module_from_spec(spec)
sys.modules[name] = mod
spec.loader.exec_module(mod)
out = getattr(mod, func)(Path(arg))
def g(o, k):
    return o.get(k) if isinstance(o, dict) else getattr(o, k, None)
if func == "surface":
    print(json.dumps(list(g(out, "names"))))
else:
    print(json.dumps({k: g(out, k) for k in ("ok", "reason", "interpreter")}))
"""

_DEP_SCRIPT = r"""
import importlib, json, sys
name = sys.argv[1]
m = importlib.import_module(name)
missing = []
for n in json.loads(sys.argv[2]):
    if hasattr(m, n):
        continue
    try:
        importlib.import_module(name + "." + n)
    except Exception:
        missing.append(n)
print(json.dumps(missing))
"""

_CALL_RE = re.compile(r"importlib\.import_module\(|module_from_spec\(|exec_module\(|\b_load\w*\(")
_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=(?!=)(.*)$")
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


@dataclass
class SurfaceReport:
    ok: bool
    findings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "findings": [dict(f) for f in self.findings]}


def _finding(kind: str, message: str) -> dict:
    return {"kind": kind, "message": message}


def _last_line(text: str) -> str:
    return next((ln.strip() for ln in reversed(text.splitlines()) if ln.strip()), "")


def _env(pythonpath: Path) -> dict:
    return {**os.environ, "PYTHONPATH": str(pythonpath), "PYTHONDONTWRITEBYTECODE": "1"}


def _slug(component_id: str) -> str:
    return component_id.removeprefix("comp-")


def _frontmatter(component_md: Path) -> list:
    if not component_md.is_file():
        return []
    lines = component_md.read_text(encoding="utf-8").splitlines()
    marks = [i for i, ln in enumerate(lines) if ln.strip() == "---"]
    if len(marks) < 2:
        return []
    return lines[marks[0] + 1:marks[1]]


def _field(lines: list, key: str):
    for ln in lines:
        if ln.startswith(key + ":"):
            return ln[len(key) + 1:].strip().strip("'\"")
    return None


def _depends_on(lines: list) -> list:
    for i, ln in enumerate(lines):
        if ln.startswith("depends_on:"):
            rest = ln[len("depends_on:"):].strip()
            if rest.startswith("["):
                return [x.strip().strip("'\"") for x in rest.strip("[]").split(",") if x.strip()]
            out = []
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if not s.startswith("-"):
                    break
                out.append(s[1:].strip().strip("'\""))
            return out
    return []


def _assets(lines: list) -> list:
    for ln in lines:
        if ln.startswith("assets:"):
            inner = ln[ln.find("[") + 1:ln.rfind("]")]
            items = [x.strip() for x in inner.split(",")]
            return [tuple(x.split(":", 1)) for x in items if x]
    return []


def _adapter(kind: str, repo_root: Path):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind}.py"
    tool_root = next((p.parent for p in Path(__file__).resolve().parents if p.name == "gen"), repo_root)
    return next((root / rel for root in (repo_root, tool_root) if (root / rel).is_file()), None)


def _run_adapter(adapter: Path, func: str, arg: Path, timeout: int):
    """Return (result, error, timed_out)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _ADAPTER_SCRIPT, str(adapter), func, str(arg)],
            env=_env(adapter.parent), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, None, True
    if proc.returncode != 0:
        return None, _last_line(proc.stderr), False
    return json.loads(_last_line(proc.stdout)), None, False


def _environment(repo_root: Path):
    """Return (interpreter, finding)."""
    adapter = _adapter("python", repo_root)
    if adapter is None:
        return None, _finding("environment", "unknown asset kind: python")
    result, err, timed_out = _run_adapter(adapter, "provision", repo_root, _PROVISION_TIMEOUT)
    if timed_out:
        return None, _finding("environment", "python environment: timed out")
    if err is not None:
        return None, _finding("environment", f"python environment: {err}")
    if not result.get("ok"):
        return None, _finding("environment", str(result.get("reason")))
    return result.get("interpreter"), None


def _dependency_findings(repo_root: Path, code_dir: Path, deps: list, interpreter: str) -> list:
    sources = [
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(code_dir.rglob("*.py"))
        if "__pycache__" not in p.relative_to(code_dir).parts
    ]
    lines = [ln for src in sources for ln in src.splitlines()]
    findings = []
    for dep_id in deps:
        dep_slug = _slug(dep_id)
        dep_mod = dep_slug.replace("-", "_")
        fm = _frontmatter(repo_root / "specs" / "components" / dep_slug / "component.md")
        if _field(fm, "sealed") == "true":
            dep_dir = repo_root / _field(fm, "source_path")
        else:
            dep_dir = repo_root / "gen" / dep_slug
        if not dep_dir.is_dir():
            continue
        quoted = re.compile(r"""(['"])(%s|%s)\1""" % (re.escape(dep_slug), re.escape(dep_mod)))
        aliases = {dep_mod}
        for ln in lines:
            m = _ASSIGN_RE.match(ln)
            if m and _CALL_RE.search(m.group(2)) and quoted.search(m.group(2)):
                aliases.add(m.group(1))
        names = set()
        for alias in aliases:
            use = re.compile(r"(?<![\w.])%s\.([A-Za-z_]\w*)" % re.escape(alias))
            for src in sources:
                names.update(n for n in use.findall(src) if not n.startswith("__"))
        proc = subprocess.run(
            [interpreter, "-c", _DEP_SCRIPT, dep_mod, json.dumps(sorted(names))],
            env=_env(dep_dir), capture_output=True, text=True, timeout=_TIMEOUT,
        )
        if proc.returncode != 0:
            continue
        for name in sorted(json.loads(_last_line(proc.stdout))):
            findings.append(_finding("dependency_name", f"{dep_slug} has no {name}, which the candidate uses"))
    return findings


def _cli_findings(spec_dir: Path, code_dir: Path, module: str, interpreter: str) -> list:
    library = spec_dir / "interface" / "library.md"
    text = library.read_text(encoding="utf-8") if library.is_file() else ""
    if not any(ln.startswith("Implements:") and _CLI_CONVENTIONS in ln for ln in text.splitlines()):
        return []
    code = f"import sys, {module}; sys.exit({module}.main([{_SMOKE_ARG!r}]))"
    try:
        proc = subprocess.run(
            [interpreter, "-c", code], env=_env(code_dir),
            capture_output=True, text=True, timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return [_finding("cli_usage", "timeout")]
    first = (proc.stderr.splitlines() or [""])[0]
    parts = []
    if proc.returncode != 2:
        parts.append(f"exit {proc.returncode}")
    if not first.startswith("usage error: "):
        parts.append("no usage error line")
    if "Traceback" in proc.stderr:
        parts.append("traceback")
    return [_finding("cli_usage", ", ".join(parts))] if parts else []


def _stated_names(interface_file: Path) -> list:
    lines = interface_file.read_text(encoding="utf-8").splitlines()
    fences = [i for i, ln in enumerate(lines) if ln.startswith("```")]
    block = lines[fences[0] + 1:fences[1]] if len(fences) >= 2 else []
    names = []
    for ln in block:
        if not ln.strip():
            continue
        head = ln.split("(", 1)[0]
        names.extend(_IDENT_RE.findall(head)[-1:])
    return names


def _asset_findings(repo_root: Path, spec_dir: Path, code_dir: Path, assets: list) -> list:
    findings = []
    provisioned = {}
    for kind, path in assets:
        adapter = _adapter(kind, repo_root)
        if adapter is None:
            findings.append(_finding("asset_error", f"unknown asset kind: {kind}"))
            continue
        if kind not in provisioned:
            result, err, timed_out = _run_adapter(adapter, "provision", repo_root, _TIMEOUT)
            if timed_out:
                provisioned[kind] = "timeout"
            elif err is not None:
                provisioned[kind] = err
            else:
                provisioned[kind] = None if result.get("ok") else str(result.get("reason"))
        if provisioned[kind] is not None:
            findings.append(_finding("asset_error", f"{path}: {provisioned[kind]}"))
            continue
        asset_file = code_dir / path
        if not asset_file.is_file():
            findings.append(_finding("asset_error", f"{path}: no such asset file"))
            continue
        file_name = path.rsplit("/", 1)[-1]
        interface_file = spec_dir / "interface" / "assets" / f"{file_name}.md"
        if not interface_file.is_file():
            findings.append(_finding("asset_error", f"{path}: no interface file interface/assets/{file_name}.md"))
            continue
        names, err, timed_out = _run_adapter(adapter, "surface", asset_file, _TIMEOUT)
        if timed_out:
            findings.append(_finding("asset_error", f"{path}: surface failed: timeout"))
            continue
        if err is not None:
            findings.append(_finding("asset_error", f"{path}: surface failed: {err}"))
            continue
        for name in sorted(set(_stated_names(interface_file)) - set(names)):
            findings.append(_finding("asset_name_missing", f"{path} has no {name}, which its interface states"))
    return findings


def check_surface(component_id: str, repo_root: Path, code_dir: Path | None = None) -> SurfaceReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    module = slug.replace("-", "_")
    code_dir = Path(code_dir) if code_dir is not None else repo_root / "gen" / slug
    spec_dir = repo_root / "specs" / "components" / slug

    interpreter, env_finding = _environment(repo_root)
    if env_finding is not None:
        return SurfaceReport(ok=False, findings=[env_finding])

    proc = subprocess.run(
        [interpreter, "-c", f"import {module}"], env=_env(code_dir),
        capture_output=True, text=True, timeout=_TIMEOUT,
    )
    if proc.returncode != 0:
        return SurfaceReport(ok=False, findings=[_finding("import_error", _last_line(proc.stderr))])

    fm = _frontmatter(spec_dir / "component.md")
    findings = []
    findings += _dependency_findings(repo_root, code_dir, _depends_on(fm), interpreter)
    findings += _cli_findings(spec_dir, code_dir, module, interpreter)
    findings += _asset_findings(repo_root, spec_dir, code_dir, _assets(fm))
    return SurfaceReport(ok=not findings, findings=findings)
