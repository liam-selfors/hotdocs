from __future__ import annotations

import hashlib
import importlib.util
import inspect
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path


class PreconditionFailure(Exception):
    """Raised when the corpus fails to satisfy an assembly precondition."""


def _get(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _slug(component_id: str) -> str:
    return component_id[len("comp-") :] if component_id.startswith("comp-") else component_id


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError("no 'gen' ancestor directory found above this module's file")


def _dependency_code_dir(repo_root: Path, slug: str, source_path: str | None, sealed: bool) -> Path | None:
    rel = Path(source_path) if (sealed and source_path) else Path("gen") / slug
    candidate = repo_root / rel
    if candidate.exists():
        return candidate
    candidate = _tool_root() / rel
    if candidate.exists():
        return candidate
    return None


def _load_module_from_dir(code_dir: Path, module_name: str):
    flat = code_dir / f"{module_name}.py"
    pkg_init = code_dir / module_name / "__init__.py"
    if flat.is_file():
        mod_file = flat
        search_locations = None
    elif pkg_init.is_file():
        mod_file = pkg_init
        search_locations = [str(code_dir / module_name)]
    else:
        return None
    spec = importlib.util.spec_from_file_location(module_name, mod_file, submodule_search_locations=search_locations)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _require_spec_linter(repo_root: Path):
    code_dir = _dependency_code_dir(repo_root, "spec-linter", None, False)
    module = _load_module_from_dir(code_dir, "spec_linter") if code_dir is not None else None
    if module is None:
        raise PreconditionFailure("spec-linter dependency code not found under gen/spec-linter/")
    return module


def _check_lint_clean(lint_fn, repo_root: Path) -> None:
    report = lint_fn(None, repo_root)
    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        findings = _get(report, "findings", []) or []
        hard_failures = sum(1 for f in findings if _get(f, "severity") == "fail")
    if hard_failures:
        raise PreconditionFailure(f"corpus failed spec-linter with {hard_failures} hard failure(s)")


def _strip_sections(body: str, excluded_headings: set[str]) -> str:
    lines = (body or "").split("\n")
    out = []
    skipping = False
    for line in lines:
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            skipping = m.group(1).strip().lower() in excluded_headings
            if skipping:
                continue
        if not skipping:
            out.append(line)
    return "\n".join(out)


def _build_spec_text(component) -> str:
    parts = []
    root_doc = _get(component, "root")
    filtered = _strip_sections(_get(root_doc, "body", ""), {"rationale", "open questions", "change log"})
    parts.append("## component.md\n\n" + filtered)
    requirements = _get(component, "requirements", {}) or {}
    for rid in sorted(requirements.keys()):
        doc = requirements[rid]
        parts.append(f"## requirements/{rid}.md\n\n" + _get(doc, "body", ""))
    return "\n\n".join(parts)


def _target_interface_docs(component) -> list:
    docs = []
    cli = _get(component, "interface_cli")
    if cli is not None:
        docs.append(cli)
    lib = _get(component, "interface_library")
    if lib is not None:
        docs.append(lib)
    for doc in (_get(component, "interface_data", {}) or {}).values():
        docs.append(doc)
    for doc in (_get(component, "interface_guarantees", {}) or {}).values():
        docs.append(doc)
    return docs


def _build_interface_text(component) -> str:
    parts = []
    cli = _get(component, "interface_cli")
    if cli is not None:
        parts.append("### interface/cli.md\n\n" + _get(cli, "body", ""))
    lib = _get(component, "interface_library")
    if lib is not None:
        parts.append("### interface/library.md\n\n" + _get(lib, "body", ""))
    data = _get(component, "interface_data", {}) or {}
    for name in sorted(data.keys()):
        parts.append(f"### interface/data/{name}.md\n\n" + _get(data[name], "body", ""))
    guarantees = _get(component, "interface_guarantees", {}) or {}
    for gid in sorted(guarantees.keys()):
        parts.append(f"### interface/guarantees/{gid}.md\n\n" + _get(guarantees[gid], "body", ""))
    return "\n\n".join(parts)


def _build_constraints_text(component) -> str:
    doc = _get(component, "constraints")
    return _get(doc, "body", "") if doc is not None else ""


_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _expand_referenced_types(dep_slug: str, dep_component, components: dict) -> tuple[str, set]:
    owned = set((_get(dep_component, "interface_data", {}) or {}).keys())
    text = _build_interface_text(dep_component)
    identifiers = sorted(set(_IDENTIFIER_RE.findall(text)) - owned)
    parts = []
    paths = set()
    for name in identifiers:
        owners = []
        for other_slug, other_component in components.items():
            if other_slug == dep_slug:
                continue
            other_data = _get(other_component, "interface_data", {}) or {}
            if name in other_data:
                owners.append((other_slug, other_data[name]))
        if len(owners) == 1:
            owner_slug, doc = owners[0]
            parts.append(f"### {name} (owned by comp-{owner_slug})\n\n" + _get(doc, "body", ""))
            doc_path = _get(doc, "path")
            if doc_path is not None:
                paths.add(Path(doc_path))
    return "\n\n".join(parts), paths


def _dependency_purpose(corpus, dep_id: str) -> str:
    graph = _get(corpus, "graph")
    if graph is None:
        return ""
    cur = graph.execute("SELECT purpose FROM component_context WHERE component_id = ?", [dep_id])
    row = cur.fetchone()
    if not row:
        return ""
    purpose = row[0]
    return (purpose or "").strip()


def _build_usage_card(repo_root: Path, slug: str, module_name: str, sealed: bool, source_path: str | None) -> str:
    code_dir = _dependency_code_dir(repo_root, slug, source_path, sealed)
    if code_dir is None:
        return ""
    try:
        module = _load_module_from_dir(code_dir, module_name)
    except Exception:
        return ""
    if module is None:
        return ""
    entries = []
    for name in sorted(vars(module).keys()):
        if name.startswith("_"):
            continue
        obj = vars(module)[name]
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if getattr(obj, "__module__", None) != module_name:
            continue
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            continue
        doc = inspect.getdoc(obj) or ""
        first_line = doc.splitlines()[0] if doc else ""
        if first_line:
            entries.append(f"- `{name}{sig}` -- {first_line}")
        else:
            entries.append(f"- `{name}{sig}`")
    rel_module_path = _rel_module_path(repo_root, code_dir)
    header = f"Importable as: `{module_name}` (module path `{rel_module_path}`)."
    if not entries:
        return header
    return header + "\n" + "\n".join(entries)


def _rel_module_path(repo_root: Path, code_dir: Path) -> str:
    try:
        rel = code_dir.relative_to(repo_root)
    except ValueError:
        try:
            rel = code_dir.relative_to(_tool_root())
        except ValueError:
            rel = code_dir
    return rel.as_posix() + "/"


def _build_vars(corpus, var_ids: list[str]) -> dict[str, str]:
    id_index = _get(corpus, "id_index", {}) or {}
    result = {}
    for vid in var_ids:
        doc = id_index.get(vid)
        if doc is not None:
            result[vid] = _get(doc, "body", "")
    return result


def _read_glossary(corpus, repo_root: Path) -> str:
    glossary_files = _get(corpus, "glossary_files", []) or []
    for p in glossary_files:
        p = Path(p)
        if p.name == "glossary.md":
            return p.read_text(encoding="utf-8")
    fallback = repo_root / "specs" / "glossary.md"
    if fallback.is_file():
        return fallback.read_text(encoding="utf-8")
    return ""


def _glossary_path(corpus, repo_root: Path) -> Path | None:
    glossary_files = _get(corpus, "glossary_files", []) or []
    for p in glossary_files:
        p = Path(p)
        if p.name == "glossary.md":
            return p
    fallback = repo_root / "specs" / "glossary.md"
    if fallback.is_file():
        return fallback
    return None


def _iter_code_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts:
            continue
        rel_parts = p.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        yield p


def _read_gen_dir(code_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not code_dir.exists():
        return result
    for p in sorted(_iter_code_files(code_dir)):
        rel = p.relative_to(code_dir).as_posix()
        try:
            result[rel] = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            result[rel] = p.read_bytes().decode("utf-8", errors="replace")
    return result


_IMPLEMENTS_LINE_RE = re.compile(r"`([^`]+)`")


def _parse_implements_line(body: str) -> list[str]:
    paths = []
    for line in (body or "").split("\n"):
        if line.strip().startswith("Implements:"):
            paths.extend(_IMPLEMENTS_LINE_RE.findall(line))
    return paths


def _implements_appendix(repo_root: Path, library_doc) -> str:
    body = _get(library_doc, "body", "") if library_doc is not None else ""
    parts = []
    for rel in _parse_implements_line(body):
        file_path = repo_root / rel
        if not file_path.is_file():
            raise PreconditionFailure(f"Implements: document not found: {rel}")
        parts.append(f"## Implements: {rel}\n\n" + file_path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def _implements_paths(repo_root: Path, library_doc) -> list[Path]:
    body = _get(library_doc, "body", "") if library_doc is not None else ""
    return [repo_root / rel for rel in _parse_implements_line(body)]


def _add_doc_path(paths: set, doc) -> None:
    if doc is None:
        return
    p = _get(doc, "path")
    if p is not None:
        paths.add(Path(p))


def _extract_covers(body: str) -> str | None:
    for line in (body or "").split("\n"):
        stripped = line.strip()
        if stripped.startswith("Covers:"):
            return stripped[len("Covers:") :].strip()
    return None


def _rel_path(p: Path, repo_root: Path) -> str | None:
    try:
        return p.relative_to(repo_root).as_posix()
    except ValueError:
        try:
            return p.relative_to(_tool_root()).as_posix()
        except ValueError:
            return None


def _compute_hash(mode: str, repo_root: Path, paths) -> str:
    h = hashlib.sha256()
    h.update(mode.encode("utf-8"))
    h.update(b"\x00")
    entries: dict[str, Path] = {}
    for p in paths:
        rel = _rel_path(Path(p), repo_root)
        if rel is None:
            continue
        entries[rel] = Path(p)
    for rel in sorted(entries):
        full = entries[rel]
        try:
            data = full.read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def _collect_hash_paths(
    *,
    repo_root: Path,
    mode: str,
    target,
    target_slug: str,
    implements_paths: list[Path],
    depends_on: list[str],
    components: dict,
    type_appendix_paths: set,
    uses_var: list[str],
    corpus,
) -> set:
    paths: set = set()

    _add_doc_path(paths, _get(target, "root"))
    _add_doc_path(paths, _get(target, "constraints"))
    for doc in (_get(target, "requirements", {}) or {}).values():
        _add_doc_path(paths, doc)
    for doc in _target_interface_docs(target):
        _add_doc_path(paths, doc)

    for p in implements_paths:
        paths.add(p)

    for dep_id in depends_on:
        dep_slug = _slug(dep_id)
        dep_component = components.get(dep_slug)
        if dep_component is None:
            continue
        dep_root = _get(dep_component, "root")
        _add_doc_path(paths, dep_root)
        for doc in _target_interface_docs(dep_component):
            _add_doc_path(paths, doc)
        dep_frontmatter = _get(dep_root, "frontmatter", {}) or {}
        dep_sealed = bool(dep_frontmatter.get("sealed", False))
        dep_source_path = dep_frontmatter.get("source_path")
        code_dir = _dependency_code_dir(repo_root, dep_slug, dep_source_path, dep_sealed)
        if code_dir is not None:
            paths.update(_iter_code_files(code_dir))

    paths.update(type_appendix_paths)

    id_index = _get(corpus, "id_index", {}) or {}
    for vid in uses_var:
        _add_doc_path(paths, id_index.get(vid))

    glossary_path = _glossary_path(corpus, repo_root)
    if glossary_path is not None:
        paths.add(glossary_path)

    if mode == "hint":
        hint_dir = repo_root / "gen" / target_slug
        if hint_dir.exists():
            paths.update(_iter_code_files(hint_dir))

    return paths


@dataclass
class SpecBundle(Mapping):
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

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __iter__(self):
        return iter(f.name for f in fields(self))

    def __len__(self):
        return len(fields(self))


@dataclass
class CriterionBundle(Mapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __iter__(self):
        return iter(f.name for f in fields(self))

    def __len__(self):
        return len(fields(self))


def _resolve_target(corpus, component_id: str):
    components = _get(corpus, "components", {}) or {}
    target_slug = _slug(component_id)
    target = components.get(target_slug)
    if target is None:
        raise ValueError(f"unknown component: {component_id}")
    return target_slug, target, components


def _target_depends_on_uses_var(target) -> tuple[list[str], list[str]]:
    root_doc = _get(target, "root")
    frontmatter = _get(root_doc, "frontmatter", {}) or {}
    depends_on = list(frontmatter.get("depends_on", []) or [])
    uses_var = list(frontmatter.get("uses_var", []) or [])
    return depends_on, uses_var


def _dependency_interfaces_contexts_usage(repo_root: Path, corpus, depends_on: list[str], components: dict):
    dependency_interfaces: dict[str, str] = {}
    dependency_context: dict[str, str] = {}
    dependency_usage: dict[str, str] = {}
    type_appendix_paths: set = set()

    for dep_id in depends_on:
        dep_slug = _slug(dep_id)
        dep_component = components.get(dep_slug)
        if dep_component is None:
            continue

        base_interface = _build_interface_text(dep_component)
        expansion, expansion_paths = _expand_referenced_types(dep_slug, dep_component, components)
        dependency_interfaces[dep_id] = base_interface + ("\n\n" + expansion if expansion else "")
        type_appendix_paths.update(expansion_paths)

        dependency_context[dep_id] = _dependency_purpose(corpus, dep_id)

        dep_root = _get(dep_component, "root")
        dep_frontmatter = _get(dep_root, "frontmatter", {}) or {}
        dep_sealed = bool(dep_frontmatter.get("sealed", False))
        dep_source_path = dep_frontmatter.get("source_path")
        dep_module_name = dep_slug.replace("-", "_")
        dependency_usage[dep_id] = _build_usage_card(repo_root, dep_slug, dep_module_name, dep_sealed, dep_source_path)

    return dependency_interfaces, dependency_context, dependency_usage, type_appendix_paths


def assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle:
    repo_root = Path(repo_root)
    if mode not in ("cold", "hint"):
        raise ValueError(f"invalid mode: {mode!r}")

    spec_linter = _require_spec_linter(repo_root)
    corpus = spec_linter.load_corpus(repo_root)
    _check_lint_clean(spec_linter.lint, repo_root)

    target_slug, target, components = _resolve_target(corpus, component_id)
    depends_on, uses_var = _target_depends_on_uses_var(target)

    spec_text = _build_spec_text(target)
    library_doc = _get(target, "interface_library")
    implements_text = _implements_appendix(repo_root, library_doc)
    interface_text = _build_interface_text(target)
    if implements_text:
        interface_text = interface_text + "\n\n" + implements_text
    constraints_text = _build_constraints_text(target)

    dependency_interfaces, dependency_context, dependency_usage, type_appendix_paths = (
        _dependency_interfaces_contexts_usage(repo_root, corpus, depends_on, components)
    )

    vars_map = _build_vars(corpus, uses_var)
    glossary_text = _read_glossary(corpus, repo_root)

    hint_code = None
    if mode == "hint":
        hint_code = _read_gen_dir(repo_root / "gen" / target_slug)

    implements_paths = _implements_paths(repo_root, library_doc)
    hash_paths = _collect_hash_paths(
        repo_root=repo_root,
        mode=mode,
        target=target,
        target_slug=target_slug,
        implements_paths=implements_paths,
        depends_on=depends_on,
        components=components,
        type_appendix_paths=type_appendix_paths,
        uses_var=uses_var,
        corpus=corpus,
    )
    spec_bundle_hash = _compute_hash(mode, repo_root, hash_paths)

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        spec=spec_text,
        interface=interface_text,
        constraints=constraints_text,
        dependency_interfaces=dependency_interfaces,
        dependency_context=dependency_context,
        dependency_usage=dependency_usage,
        vars=vars_map,
        glossary=glossary_text,
        hint_code=hint_code,
    )


def assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle:
    repo_root = Path(repo_root)

    spec_linter = _require_spec_linter(repo_root)
    corpus = spec_linter.load_corpus(repo_root)
    _check_lint_clean(spec_linter.lint, repo_root)

    target_slug, target, components = _resolve_target(corpus, component_id)

    acceptance = _get(target, "acceptance", {}) or {}
    criterion_doc = acceptance.get(criterion_id)
    if criterion_doc is None:
        raise ValueError(f"unknown criterion: {criterion_id}")
    criterion_text = _get(criterion_doc, "body", "")

    covers = _extract_covers(criterion_text) or ""
    requirements = _get(target, "requirements", {}) or {}
    requirement_doc = requirements.get(covers) if covers else None
    requirement_text = _get(requirement_doc, "body", "") if requirement_doc is not None else ""

    library_doc = _get(target, "interface_library")
    implements_text = _implements_appendix(repo_root, library_doc)
    interface_text = _build_interface_text(target)
    if implements_text:
        interface_text = interface_text + "\n\n" + implements_text

    glossary_text = _read_glossary(corpus, repo_root)

    depends_on, _uses_var = _target_depends_on_uses_var(target)
    dependency_interfaces: dict[str, str] = {}
    for dep_id in depends_on:
        dep_slug = _slug(dep_id)
        dep_component = components.get(dep_slug)
        if dep_component is None:
            continue
        base_interface = _build_interface_text(dep_component)
        expansion, _paths = _expand_referenced_types(dep_slug, dep_component, components)
        dependency_interfaces[dep_id] = base_interface + ("\n\n" + expansion if expansion else "")

    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=criterion_text,
        requirement_text=requirement_text,
        interface=interface_text,
        glossary=glossary_text,
        dependency_interfaces=dependency_interfaces,
    )


from .cli import main  # noqa: E402

__all__ = ["assemble", "assemble_criterion", "SpecBundle", "CriterionBundle", "PreconditionFailure", "main"]