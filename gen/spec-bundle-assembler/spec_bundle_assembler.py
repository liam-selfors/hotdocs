"""Spec Bundle Assembler.

Assembles a component's full generation input (``SpecBundle``) and the
narrower per-criterion input (``CriterionBundle``) from the spec corpus.
All corpus structure is read through ``spec_linter.load_corpus``'s returned
``Corpus``/``Component`` objects (R-ASSEMBLE-012); dependency ``Purpose``
text is read through ``graph_query_engine``'s ``component_context`` view
(R-ASSEMBLE-010).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import inspect
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

__all__ = [
    "SpecBundle",
    "CriterionBundle",
    "PreconditionFailure",
    "UnknownComponentError",
    "UnknownCriterionError",
    "assemble",
    "assemble_criterion",
    "main",
]

_GEN_DIR = Path(__file__).resolve().parent.parent

MODES = ("cold", "hint")

# Sections of the target's own component.md excluded from the bundle (R-ASSEMBLE-001).
_EXCLUDED_TARGET_SECTIONS = {"rationale", "open questions", "change log", "changelog"}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PreconditionFailure(Exception):
    """R-ASSEMBLE-005. Corpus does not pass spec-linter at hard-fail severity."""

    def __init__(self, findings: list):
        self.findings = list(findings)
        super().__init__(
            f"corpus is not lint-clean: {len(self.findings)} fail-severity finding(s)"
        )


class UnknownComponentError(ValueError):
    """No component with the given id exists in the corpus."""


class UnknownCriterionError(ValueError):
    """No acceptance criterion with the given id exists on the component."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


class _Mapping:
    """Dict-style read access on top of a dataclass."""

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def __getitem__(self, key: str) -> Any:
        if key not in self._field_names():
            raise KeyError(key)
        return getattr(self, key)

    def __contains__(self, key: object) -> bool:
        return key in self._field_names()

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key) if key in self._field_names() else default

    def keys(self):
        return [f.name for f in fields(self)]

    def _field_names(self) -> set:
        return {f.name for f in fields(self)}


@dataclass
class SpecBundle(_Mapping):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: dict | None = None


@dataclass
class CriterionBundle(_Mapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dependency loading
# ---------------------------------------------------------------------------


def _exec_module_file(name: str, path: Path, is_package: bool):
    spec = importlib.util.spec_from_file_location(
        name,
        str(path),
        submodule_search_locations=[str(path.parent)] if is_package else None,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Registered before exec_module: dataclasses resolve sys.modules[cls.__module__].
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _module_file_in(directory: Path, module_name: str) -> tuple[Path, bool] | None:
    flat = directory / f"{module_name}.py"
    if flat.is_file():
        return flat, False
    pkg = directory / module_name / "__init__.py"
    if pkg.is_file():
        return pkg, True
    return None


def _load_dependency(module_name: str, slug: str, repo_root: Path | None = None):
    if module_name in sys.modules:
        return sys.modules[module_name]
    try:
        return importlib.import_module(module_name)
    except ImportError:
        pass
    candidates = [_GEN_DIR / slug]
    if repo_root is not None:
        candidates.append(Path(repo_root).resolve() / "gen" / slug)
    for directory in candidates:
        found = _module_file_in(directory, module_name)
        if found is not None:
            return _exec_module_file(module_name, found[0], found[1])
    raise ImportError(f"cannot locate dependency module {module_name!r} ({slug})")


def _deps(repo_root: Path):
    # graph_query_engine first, so spec_linter's own import of it resolves.
    gqe = _load_dependency("graph_query_engine", "graph-query-engine", repo_root)
    linter = _load_dependency("spec_linter", "spec-linter", repo_root)
    return linter, gqe


# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _frontmatter(comp) -> dict:
    root = getattr(comp, "root", None)
    return dict(getattr(root, "frontmatter", None) or {}) if root is not None else {}


def _component_id(comp) -> str:
    cid = _frontmatter(comp).get("id")
    return str(cid) if cid else f"comp-{comp.name}"


def _find_component(corpus, component_id: str):
    for name in sorted(corpus.components):
        comp = corpus.components[name]
        if _component_id(comp) == component_id:
            return comp
    return corpus.components.get(_slug(component_id))


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _doc_text(doc) -> str:
    if doc is None:
        return ""
    return (getattr(doc, "body", None) or "").strip()


def _rel(doc) -> str:
    rel = getattr(doc, "rel_path", None) or str(getattr(doc, "path", ""))
    return rel.replace("\\", "/")


def _interface_label(doc) -> str:
    rel = _rel(doc)
    idx = rel.find("/interface/")
    if idx >= 0:
        return rel[idx + 1:]
    if rel.startswith("interface/"):
        return rel
    return "interface/" + Path(rel).name


def _render_interface(comp) -> str:
    if comp is None:
        return ""
    docs = []
    for doc in (comp.interface_cli, comp.interface_library):
        if doc is not None:
            docs.append(doc)
    for group in (comp.interface_data, comp.interface_guarantees):
        docs.extend(sorted((group or {}).values(), key=_interface_label))
    return "\n\n".join(f"### {_interface_label(d)}\n\n{_doc_text(d)}" for d in docs)


def _strip_target_sections(body: str) -> str:
    out: list[str] = []
    skipping: int | None = None
    fence: str | None = None
    for line in body.splitlines(keepends=True):
        stripped = line.lstrip()
        if fence is None and (stripped.startswith("```") or stripped.startswith("~~~")):
            fence = stripped[:3]
        elif fence is not None and stripped.startswith(fence):
            fence = None
        elif fence is None:
            m = _HEADING_RE.match(line.rstrip("\n"))
            if m:
                level = len(m.group(1))
                title = " ".join(m.group(2).strip().lower().split())
                if skipping is not None and level <= skipping:
                    skipping = None
                if skipping is None and level == 2 and title in _EXCLUDED_TARGET_SECTIONS:
                    skipping = level
        if skipping is None:
            out.append(line)
    return "".join(out).strip()


def _render_spec(comp) -> str:
    parts = [_strip_target_sections(getattr(comp.root, "body", "") or "")]
    reqs = comp.requirements or {}
    for key in sorted(reqs):
        doc = reqs[key]
        header = getattr(doc, "doc_id", None) or Path(_rel(doc)).stem or key
        parts.append(f"### {header}\n\n{_doc_text(doc)}")
    return "\n\n".join(p for p in parts if p)


def _read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _glossary(corpus, repo_root: Path) -> str:
    path = repo_root / "specs" / "glossary.md"
    if path.is_file():
        return _read_text(path)
    files = sorted(getattr(corpus, "glossary_files", None) or [], key=str)
    return "\n\n".join(_read_text(Path(p)) for p in files)


def _check_lint(linter, repo_root: Path) -> None:
    report = linter.lint(None, repo_root)
    failures = []
    for f in getattr(report, "findings", None) or []:
        severity = f.get("severity") if isinstance(f, dict) else getattr(f, "severity", None)
        if severity == "fail":
            failures.append(f)
    if failures:
        raise PreconditionFailure(failures)


# ---------------------------------------------------------------------------
# Graph views
# ---------------------------------------------------------------------------


def _graph(corpus, gqe, repo_root: Path):
    con = getattr(corpus, "graph", None)
    if con is None:
        import duckdb

        con = duckdb.connect()
        try:
            con.execute("LOAD yaml")
        except Exception:
            con.execute("INSTALL yaml FROM community")
            con.execute("LOAD yaml")
    try:
        con.execute("SELECT 1 FROM component_context LIMIT 0")
        con.execute("SELECT 1 FROM edges LIMIT 0")
    except Exception:
        gqe.load_views(con, repo_root)
    return con


def _purpose(con, component_id: str) -> str:
    row = con.execute(
        "SELECT purpose FROM component_context WHERE component_id = ? LIMIT 1",
        [component_id],
    ).fetchone()
    return (row[0] or "") if row else ""


# ---------------------------------------------------------------------------
# Referenced-type expansion (R-ASSEMBLE-013)
# ---------------------------------------------------------------------------


def _type_owner_index(corpus) -> dict[str, list]:
    index: dict[str, list] = {}
    for name in sorted(corpus.components):
        comp = corpus.components[name]
        seen: set[str] = set()
        for doc in sorted((comp.interface_data or {}).values(), key=_interface_label):
            path = Path(_rel(doc))
            if path.suffix != ".md" or path.stem in seen:
                continue
            seen.add(path.stem)
            index.setdefault(path.stem, []).append((comp, doc))
    return index


def _expand_referenced_types(dep, rendered: str, index: dict[str, list]) -> str:
    owned = {Path(_rel(d)).stem for d in (dep.interface_data or {}).values()}
    dep_id = _component_id(dep)
    sections = []
    for token in sorted(set(_IDENT_RE.findall(rendered))):
        if token in owned:
            continue
        owners = index.get(token) or []
        if len(owners) != 1:
            continue  # unresolved or ambiguous: never guess
        owner, doc = owners[0]
        if owner is dep:
            continue
        sections.append(
            f"### Referenced type `{token}` — owned by `{_component_id(owner)}` "
            f"({_interface_label(doc)}), not by `{dep_id}`\n\n{_doc_text(doc)}"
        )
    if not sections:
        return rendered
    return "\n\n".join([rendered] + sections) if rendered else "\n\n".join(sections)


def _dependency_interfaces(corpus, dep_ids: list[str]) -> dict[str, str]:
    index = _type_owner_index(corpus)
    result: dict[str, str] = {}
    for dep_id in dep_ids:
        dep = _find_component(corpus, dep_id)
        if dep is None:
            result[dep_id] = ""
            continue
        result[dep_id] = _expand_referenced_types(dep, _render_interface(dep), index)
    return result


# ---------------------------------------------------------------------------
# Usage cards (R-ASSEMBLE-011)
# ---------------------------------------------------------------------------

_usage_cache: dict[tuple, str] = {}


def _locate_code(dep, repo_root: Path) -> tuple[str, Path, bool, Path] | None:
    """Return (module_name, file, is_package, display_dir) for a dependency's real code."""
    slug = dep.name
    module_name = slug.replace("-", "_")
    fm = _frontmatter(dep)
    source_path = fm.get("source_path")
    if source_path and (fm.get("sealed") or fm.get("status") == "sealed" or True):
        sp = (repo_root / str(source_path)).resolve()
        if sp.is_file() and sp.suffix == ".py":
            if sp.name == "__init__.py":
                return sp.parent.name, sp, True, sp.parent.parent
            return sp.stem, sp, False, sp.parent
        if sp.is_dir():
            if (sp / "__init__.py").is_file():
                return sp.name, sp / "__init__.py", True, sp.parent
            found = _module_file_in(sp, module_name)
            if found is not None:
                return module_name, found[0], found[1], sp
    gen_dir = repo_root / "gen" / slug
    found = _module_file_in(gen_dir, module_name)
    if found is not None:
        return module_name, found[0], found[1], gen_dir
    return None


def _first_doc_line(obj) -> str:
    doc = inspect.getdoc(obj)
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip()


def _usage_card(dep, repo_root: Path) -> str:
    located = _locate_code(dep, repo_root)
    if located is None:
        return ""
    module_name, path, is_package, display_dir = located
    try:
        key = (str(path), path.stat().st_mtime_ns, str(display_dir))
    except OSError:
        return ""
    if key in _usage_cache:
        return _usage_cache[key]

    load_name = f"_hotdocs_usage__{module_name}"
    try:
        sys.modules.pop(load_name, None)
        module = _exec_module_file(load_name, path, is_package)
    except BaseException:
        _usage_cache[key] = ""
        return ""

    explicit = getattr(module, "__all__", None)
    if explicit is not None:
        names = sorted(str(n) for n in explicit)
    else:
        names = sorted(n for n in vars(module) if not n.startswith("_"))

    lines = []
    for name in names:
        obj = getattr(module, name, None)
        if obj is None or not (inspect.isfunction(obj) or inspect.isclass(obj) or callable(obj)):
            continue
        if explicit is None and getattr(obj, "__module__", None) != module.__name__:
            continue
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            sig = "(...)"
        doc = _first_doc_line(obj)
        lines.append(f"- `{name}{sig}`" + (f" -- {doc}" if doc else ""))

    try:
        shown = display_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        shown = display_dir.as_posix()
    header = f"Importable as: `{module_name}` (module path `{shown}/`)."
    card = "\n".join([header] + lines)
    _usage_cache[key] = card
    return card


# ---------------------------------------------------------------------------
# hint_code (R-ASSEMBLE-008)
# ---------------------------------------------------------------------------


def _hint_code(slug: str, repo_root: Path) -> dict[str, str]:
    root = repo_root / "gen" / slug
    result: dict[str, str] = {}
    if not root.is_dir():
        return result
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts or path.suffix in (".pyc", ".pyo"):
            continue
        try:
            result[rel.as_posix()] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return result


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _hash(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle:
    """Assemble one component's SpecBundle (R-ASSEMBLE-001..013)."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    repo_root = Path(repo_root).resolve()
    linter, gqe = _deps(repo_root)
    _check_lint(linter, repo_root)
    corpus = linter.load_corpus(repo_root)

    comp = _find_component(corpus, component_id)
    if comp is None or comp.root is None:
        raise UnknownComponentError(f"unknown component id: {component_id}")
    fm = _frontmatter(comp)
    dep_ids = _as_list(fm.get("depends_on"))

    con = _graph(corpus, gqe, repo_root) if dep_ids else None
    dependency_context = {d: _purpose(con, d) for d in dep_ids}
    dependency_usage = {}
    for d in dep_ids:
        dep = _find_component(corpus, d)
        dependency_usage[d] = _usage_card(dep, repo_root) if dep is not None else ""

    var_contents: dict[str, str] = {}
    for var_id in _as_list(fm.get("uses_var")):
        doc = corpus.id_index.get(var_id)
        if doc is not None:
            var_contents[var_id] = _read_text(Path(doc.path))

    fields_: dict[str, Any] = {
        "component_id": _component_id(comp),
        "spec": _render_spec(comp),
        "interface": _render_interface(comp),
        "constraints": _doc_text(comp.constraints),
        "dependency_interfaces": _dependency_interfaces(corpus, dep_ids),
        "dependency_context": dependency_context,
        "dependency_usage": dependency_usage,
        "vars": var_contents,
        "glossary": _glossary(corpus, repo_root),
    }
    # hint_code is excluded from the hash so cold/hint non-hint_code fields stay identical.
    bundle_hash = _hash(fields_)
    hint = _hint_code(comp.name, repo_root) if mode == "hint" else None
    return SpecBundle(spec_bundle_hash=bundle_hash, hint_code=hint, **fields_)


def _find_doc(group: dict, wanted: str):
    if wanted in group:
        return group[wanted]
    for key in sorted(group):
        doc = group[key]
        if getattr(doc, "doc_id", None) == wanted or Path(_rel(doc)).stem == wanted:
            return doc
    return None


def _covers(con, criterion_id: str, doc) -> str:
    try:
        row = con.execute(
            "SELECT target_id FROM edges WHERE source_id = ? AND edge_type = 'covers' "
            "ORDER BY target_id LIMIT 1",
            [criterion_id],
        ).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    m = re.search(r"Covers:?\**\s*`?([A-Za-z0-9-]+)`?", getattr(doc, "body", "") or "")
    return m.group(1) if m else ""


def assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle:
    """Assemble the narrower CriterionBundle for one acceptance criterion (R-ASSEMBLE-009)."""
    repo_root = Path(repo_root).resolve()
    linter, gqe = _deps(repo_root)
    _check_lint(linter, repo_root)
    corpus = linter.load_corpus(repo_root)

    comp = _find_component(corpus, component_id)
    if comp is None or comp.root is None:
        raise UnknownComponentError(f"unknown component id: {component_id}")
    crit = _find_doc(comp.acceptance or {}, criterion_id)
    if crit is None:
        raise UnknownCriterionError(f"unknown criterion id {criterion_id} on {component_id}")

    con = _graph(corpus, gqe, repo_root)
    covers = _covers(con, criterion_id, crit)
    req = _find_doc(comp.requirements or {}, covers) if covers else None
    if req is None and covers:
        req = corpus.id_index.get(covers)

    dep_ids = _as_list(_frontmatter(comp).get("depends_on"))
    return CriterionBundle(
        component_id=_component_id(comp),
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=_doc_text(crit),
        requirement_text=_doc_text(req),
        interface=_render_interface(comp),
        glossary=_glossary(corpus, repo_root),
        dependency_interfaces=_dependency_interfaces(corpus, dep_ids),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs assemble")
    parser.add_argument("component_id")
    parser.add_argument("--mode", default="cold")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", default="text", choices=["json", "text"])
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.mode not in MODES:
        print(f"error: --mode must be one of {', '.join(MODES)}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root) if args.repo_root else _default_repo_root()

    try:
        bundle = assemble(args.component_id, repo_root, mode=args.mode)
    except PreconditionFailure as exc:
        print(f"error: {exc}", file=sys.stderr)
        for f in exc.findings:
            if isinstance(f, dict):
                rule, file_, line, msg = f.get("rule_id"), f.get("file"), f.get("line"), f.get("message")
            else:
                rule, file_, line, msg = f.rule_id, f.file, f.line, f.message
            print(f"  {file_}:{line}: {rule}: {msg}", file=sys.stderr)
        return 1
    except (UnknownComponentError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"component_id:     {bundle.component_id}")
        print(f"mode:             {args.mode}")
        print(f"spec_bundle_hash: {bundle.spec_bundle_hash}")
        print(f"spec:             {len(bundle.spec)} chars")
        print(f"interface:        {len(bundle.interface)} chars")
        print(f"constraints:      {len(bundle.constraints)} chars")
        print(f"dependencies:     {', '.join(bundle.dependency_interfaces) or '(none)'}")
        print(f"vars:             {', '.join(bundle.vars) or '(none)'}")
        print(f"glossary:         {len(bundle.glossary)} chars")
        if bundle.hint_code is not None:
            print(f"hint_code:        {len(bundle.hint_code)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())