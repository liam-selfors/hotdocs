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
_LOAD_CALLS = ("importlib.import_module(", "module_from_spec(", "exec_module(")
_LOAD_FN_RE = re.compile(r"(?<!\w)_load\w*\(")
_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)(.*)$")
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

_ADAPTER_SCRIPT = r'''
import importlib.util, json, sys
from pathlib import Path
p, fn, arg = sys.argv[1:4]
spec = importlib.util.spec_from_file_location(Path(p).stem, p)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
r = getattr(m, fn)(Path(arg))
def g(k):
    return r.get(k) if isinstance(r, dict) else getattr(r, k, None)
if fn == "surface":
    out = list(g("names"))
else:
    out = {k: g(k) for k in ("ok", "reason", "interpreter")}
print(json.dumps(out))
'''

_DEP_SCRIPT = r'''
import importlib, json, sys
mod = sys.argv[1]
names = json.loads(sys.argv[2])
m = importlib.import_module(mod)
missing = []
for n in names:
    if hasattr(m, n):
        continue
    try:
        importlib.import_module(mod + "." + n)
    except Exception:
        missing.append(n)
print(json.dumps(missing))
'''


@dataclass
class SurfaceReport:
    ok: bool
    findings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "findings": [dict(f) for f in self.findings]}


def _tool_root():
    for p in Path(__file__).resolve().parents:
        if p.name == "gen":
            return p.parent
    return None


def _find_adapter(repo_root: Path, kind: str):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    roots = [repo_root]
    tool = _tool_root()
    if tool is not None:
        roots.append(tool)
    for root in roots:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def _env(pythonpath: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pythonpath)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run(cmd: list, pythonpath: Path, timeout: int):
    try:
        return subprocess.run(
            cmd,
            env=_env(pythonpath),
            cwd=str(pythonpath),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _call_adapter(adapter: Path, fn: str, arg: Path, timeout: int):
    """Returns ("ok", value), ("failed", stderr line) or ("timeout", None)."""
    proc = _run(
        [sys.executable, "-c", _ADAPTER_SCRIPT, str(adapter), fn, str(arg)],
        adapter.parent,
        timeout,
    )
    if proc is None:
        return "timeout", None
    if proc.returncode != 0:
        return "failed", _last_line(proc.stderr)
    return "ok", json.loads(_last_line(proc.stdout))


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


def _fm_value(lines: list, key: str) -> str:
    for line in lines:
        if line.startswith(f"{key}:"):
            return line[len(key) + 1:].strip().strip("'\"")
    return ""


def _depends_on(lines: list) -> list:
    for i, line in enumerate(lines):
        if line.startswith("depends_on:"):
            rest = line[len("depends_on:"):].strip()
            if rest:
                items = (x.strip().strip("'\"") for x in rest.strip("[]").split(","))
                return [x for x in items if x]
            out = []
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if s.startswith("-"):
                    out.append(s[1:].strip().strip("'\""))
                elif s:
                    break
            return out
    return []


def _assets(lines: list) -> list:
    for line in lines:
        if line.startswith("assets:"):
            inner = line[line.find("[") + 1:line.rfind("]")]
            out = []
            for item in inner.split(","):
                item = item.strip()
                if item:
                    kind, _, path = item.partition(":")
                    out.append((kind.strip(), path.strip()))
            return out
    return []


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _sources(code_dir: Path) -> list:
    texts = []
    for p in sorted(code_dir.rglob("*.py")):
        if "__pycache__" in p.relative_to(code_dir).parts:
            continue
        texts.append(p.read_text(encoding="utf-8", errors="replace"))
    return texts


def _uses(texts: list, dep_slug: str, dep_module: str) -> list:
    quoted = re.compile(r"""(['"])(%s|%s)\1""" % (re.escape(dep_slug), re.escape(dep_module)))
    aliases = {dep_module}
    for text in texts:
        for line in text.splitlines():
            m = _ASSIGN_RE.match(line)
            if not m:
                continue
            rhs = m.group(2)
            calls = any(c in rhs for c in _LOAD_CALLS) or _LOAD_FN_RE.search(rhs)
            if calls and quoted.search(rhs):
                aliases.add(m.group(1))
    names = set()
    for alias in aliases:
        use_re = re.compile(r"(?<![\w.])%s\.([A-Za-z_][A-Za-z0-9_]*)" % re.escape(alias))
        for text in texts:
            for name in use_re.findall(text):
                if not name.startswith("__"):
                    names.add(name)
    return sorted(names)


def _stated_names(text: str) -> list:
    lines = text.splitlines()
    names = []
    inside = False
    for line in lines:
        if line.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if not inside or not line.strip():
            continue
        head = line[:line.index("(")] if "(" in line else line
        idents = _IDENT_RE.findall(head)
        if idents:
            names.append(idents[-1])
    return names


def check_surface(component_id: str, repo_root: Path, code_dir: Path | None = None) -> SurfaceReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    module = slug.replace("-", "_")
    code_dir = Path(code_dir) if code_dir is not None else repo_root / "gen" / slug
    spec_dir = repo_root / "specs" / "components" / slug
    findings: list = []

    def done() -> SurfaceReport:
        return SurfaceReport(ok=not findings, findings=findings)

    # Check 0: environment (R-SURF-006)
    py_adapter = _find_adapter(repo_root, "python")
    if py_adapter is None:
        findings.append({"kind": "environment", "message": "unknown asset kind: python"})
        return done()
    status, value = _call_adapter(py_adapter, "provision", repo_root, _PROVISION_TIMEOUT)
    if status == "timeout":
        findings.append({"kind": "environment", "message": "python environment: timed out"})
        return done()
    if status == "failed":
        findings.append({"kind": "environment", "message": f"python environment: {value}"})
        return done()
    if not value.get("ok"):
        findings.append({"kind": "environment", "message": str(value.get("reason"))})
        return done()
    interp = value.get("interpreter")

    # Check 1: import (R-SURF-001)
    proc = _run([interp, "-c", f"import {module}"], code_dir, _TIMEOUT)
    if proc is None:
        findings.append({"kind": "import_error", "message": "timeout"})
        return done()
    if proc.returncode != 0:
        findings.append({"kind": "import_error", "message": _last_line(proc.stderr)})
        return done()

    fm = _frontmatter(spec_dir / "component.md")

    # Check 2: dependency names (R-SURF-002)
    texts = _sources(code_dir)
    for dep in _depends_on(fm):
        dep_slug = _slug(dep)
        dep_module = dep_slug.replace("-", "_")
        dep_fm = _frontmatter(repo_root / "specs" / "components" / dep_slug / "component.md")
        if _fm_value(dep_fm, "sealed") == "true":
            dep_dir = repo_root / _fm_value(dep_fm, "source_path")
        else:
            dep_dir = repo_root / "gen" / dep_slug
        if not dep_dir.is_dir():
            continue
        names = _uses(texts, dep_slug, dep_module)
        if not names:
            continue
        proc = _run([interp, "-c", _DEP_SCRIPT, dep_module, json.dumps(names)], dep_dir, _TIMEOUT)
        if proc is None or proc.returncode != 0:
            continue
        for name in sorted(json.loads(_last_line(proc.stdout))):
            findings.append({
                "kind": "dependency_name",
                "message": f"{dep_slug} has no {name}, which the candidate uses",
            })

    # Check 3: command line (R-SURF-003)
    library = spec_dir / "interface" / "library.md"
    lib_text = library.read_text(encoding="utf-8") if library.is_file() else ""
    if any(
        ln.lstrip().startswith("Implements:") and _CLI_CONVENTIONS in ln
        for ln in lib_text.splitlines()
    ):
        script = f"import sys\nimport {module}\nsys.exit({module}.main(['--hotdocs-smoke-unknown']))"
        proc = _run([interp, "-c", script], code_dir, _TIMEOUT)
        if proc is None:
            findings.append({"kind": "cli_usage", "message": "timeout"})
        else:
            parts = []
            if proc.returncode != 2:
                parts.append(f"exit {proc.returncode}")
            err_lines = proc.stderr.splitlines()
            first = err_lines[0] if err_lines else ""
            if not first.startswith("usage error: "):
                parts.append("no usage error line")
            if "Traceback" in proc.stderr:
                parts.append("traceback")
            if parts:
                findings.append({"kind": "cli_usage", "message": ", ".join(parts)})

    # Check 4: assets (R-SURF-005)
    provisioned: dict = {}
    for kind, path in _assets(fm):
        adapter = _find_adapter(repo_root, kind)
        if adapter is None:
            findings.append({"kind": "asset_error", "message": f"unknown asset kind: {kind}"})
            continue
        if kind not in provisioned:
            p_status, p_value = _call_adapter(adapter, "provision", repo_root, _TIMEOUT)
            if p_status == "ok":
                provisioned[kind] = p_value
            else:
                provisioned[kind] = {
                    "ok": False,
                    "reason": f"{kind} environment: {p_value if p_status == 'failed' else 'timed out'}",
                }
        prov = provisioned[kind]
        if not prov.get("ok"):
            findings.append({"kind": "asset_error", "message": f"{path}: {prov.get('reason')}"})
            continue
        asset_file = code_dir / path
        if not asset_file.is_file():
            findings.append({"kind": "asset_error", "message": f"{path}: no such asset file"})
            continue
        file_name = path.rsplit("/", 1)[-1]
        iface = spec_dir / "interface" / "assets" / f"{file_name}.md"
        if not iface.is_file():
            findings.append({
                "kind": "asset_error",
                "message": f"{path}: no interface file interface/assets/{file_name}.md",
            })
            continue
        s_status, s_value = _call_adapter(adapter, "surface", asset_file, _TIMEOUT)
        if s_status == "timeout":
            findings.append({"kind": "asset_error", "message": f"{path}: surface failed: timeout"})
            continue
        if s_status == "failed":
            findings.append({"kind": "asset_error", "message": f"{path}: surface failed: {s_value}"})
            continue
        provided = set(s_value)
        stated = set(_stated_names(iface.read_text(encoding="utf-8")))
        for name in sorted(stated - provided):
            findings.append({
                "kind": "asset_name_missing",
                "message": f"{path} has no {name}, which its interface states",
            })

    return done()
