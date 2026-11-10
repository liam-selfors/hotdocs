"""Spec Bundle Assembler.

Assembles a component's full generation input (SpecBundle) or a single
criterion's narrower input (CriterionBundle) from the spec corpus at
repo_root, reusing spec-linter's own parsed Corpus for all structural
reads (R-ASSEMBLE-012).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from collections.abc import Mapping
from pathlib import Path


class PreconditionFailure(Exception):
    """Raised when the corpus is not in a state assembly can proceed from."""


# --------------------------------------------------------------------------
# Bundle data types
# --------------------------------------------------------------------------


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
        return iter(self.__dataclass_fields__)

    def __len__(self):
        return len(self.__dataclass_fields__)


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
        return iter(self.__dataclass_fields__)

    def __len__(self):
        return len(self.__dataclass_fields__)


# --------------------------------------------------------------------------
# Dual dict-or-attribute access for values read from dependency calls
# --------------------------------------------------------------------------


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _strip_prefix(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


# --------------------------------------------------------------------------
# Dynamic dependency loading (R-ASSEMBLE-015 and the generic repo_root /
# tool_root fallback rule)
# --------------------------------------------------------------------------


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise PreconditionFailure("could not locate tool root (no 'gen' ancestor directory)")


def _resolve_code_dir(repo_root: Path, rel_path: str) -> Path | None:
    candidate = repo_root / rel_path
    if candidate.is_dir():
        return candidate
    tool_candidate = _tool_root() / rel_path
    if tool_candidate.is_dir():
        return tool_candidate
    return None


def _load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    # Must be registered before exec_module: dataclasses defined in the
    # loaded module resolve their own annotations via sys.modules[__module__]
    # while their class body executes.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep_module(repo_root: Path, module_name: str, rel_dir: str):
    base = _resolve_code_dir(repo_root, rel_dir)
    if base is None:
        return None
    flat = base / f"{module_name}.py"
    pkg = base / module_name / "__init__.py"
    if flat.is_file():
        path = flat
    elif pkg.is_file():
        path = pkg
    else:
        return None
    return _load_module_from_path(module_name, path)


def _load_tooling(repo_root: Path):
    spec_linter = _load_dep_module(repo_root, "spec_linter", "gen/spec-linter")
    graph_query_engine = _load_dep_module(repo_root, "graph_query_engine", "gen/graph-query-engine")
    if spec_linter is None or graph_query_engine is None:
        raise PreconditionFailure("spec-linter or graph-query-engine is not available")
    return spec_linter, graph_query_engine


def _ensure_lint_clean(spec_linter, repo_root: Path) -> None:
    report = spec_linter.lint(None, repo_root)
    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        summary = _get(report, "summary", {}) or {}
        hard_failures = _get(summary, "hard_failures", 0) or 0
    if hard_failures:
        raise PreconditionFailure(
            f"corpus failed spec-linter with {hard_failures} hard failure(s)"
        )


# --------------------------------------------------------------------------
# Filesystem helpers
# --------------------------------------------------------------------------


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _walk_code_dir(base: Path) -> list:
    if not base.is_dir():
        return []
    files = []
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(base).parts
        if any(part.startswith(".") or part == "__pycache__" for part in rel_parts):
            continue
        files.append(p)
    return files


def _rel_posix(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel = Path(os.path.relpath(path, repo_root))
    return rel.as_posix()


def _compute_hash(mode: str, file_paths, repo_root: Path) -> str:
    h = hashlib.sha256()
    h.update(mode.encode("utf-8"))
    h.update(b"\x00")
    ordered = sorted(file_paths, key=lambda p: _rel_posix(p, repo_root))
    for path in ordered:
        rel = _rel_posix(path, repo_root)
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(path.read_bytes())
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


# --------------------------------------------------------------------------
# Markdown helpers
# --------------------------------------------------------------------------


def _strip_sections(text: str, excluded: set) -> str:
    lines = text.split("\n")
    out = []
    skip = False
    for line in lines:
        if line.startswith("## "):
            skip = line[3:].strip() in excluded
        if not skip:
            out.append(line)
    return "\n".join(out)


_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_IMPLEMENTS_PATH_RE = re.compile(r"`([^`]+)`")


def _build_implements(lib_doc, repo_root: Path):
    if lib_doc is None:
        return "", []
    body = _get(lib_doc, "body", "") or ""
    paths = []
    chunks = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("Implements:"):
            for name in _IMPLEMENTS_PATH_RE.findall(stripped):
                target_path = repo_root / name
                if not target_path.is_file():
                    raise PreconditionFailure(f"Implements target not found: {name}")
                content = _read_text(target_path)
                chunks.append(f"\n## Implements: {name}\n\n{content}")
                paths.append(target_path)
    return "".join(chunks), paths


def _iter_interface_docs(component):
    docs = []
    cli_doc = _get(component, "interface_cli")
    if cli_doc:
        docs.append(cli_doc)
    lib_doc = _get(component, "interface_library")
    if lib_doc:
        docs.append(lib_doc)
    data = _get(component, "interface_data", {}) or {}
    for key in sorted(data.keys()):
        docs.append(data[key])
    guarantees = _get(component, "interface_guarantees", {}) or {}
    for key in sorted(guarantees.keys()):
        docs.append(guarantees[key])
    return docs


def _build_plain_interface(component):
    parts = []
    paths = []
    for doc in _iter_interface_docs(component):
        body = (_get(doc, "body", "") or "").strip()
        if body:
            parts.append(body)
        path = _get(doc, "path")
        if path:
            paths.append(Path(path))
    return "\n\n".join(parts), paths


def _build_target_interface(component, repo_root: Path):
    text, paths = _build_plain_interface(component)
    lib_doc = _get(component, "interface_library")
    implements_text, implements_paths = _build_implements(lib_doc, repo_root)
    return text + implements_text, paths + implements_paths


def _build_type_owner_index(corpus):
    index = {}
    for slug, comp in (_get(corpus, "components", {}) or {}).items():
        data = _get(comp, "interface_data", {}) or {}
        for type_name in data.keys():
            index.setdefault(type_name, []).append(slug)
    return index


def _resolve_referenced_types(dep_component, interface_text, type_index, corpus):
    owned = set((_get(dep_component, "interface_data", {}) or {}).keys())
    identifiers = sorted(set(_IDENTIFIER_RE.findall(interface_text)))
    chunks = []
    paths = []
    for identifier in identifiers:
        if identifier in owned:
            continue
        owners = type_index.get(identifier, [])
        if len(owners) != 1:
            continue
        owner_component = (_get(corpus, "components", {}) or {}).get(owners[0])
        if owner_component is None:
            continue
        type_doc = (_get(owner_component, "interface_data", {}) or {}).get(identifier)
        if type_doc is None:
            continue
        body = (_get(type_doc, "body", "") or "").strip()
        chunks.append(f"\n\n## Type: {identifier} (owned by comp-{owners[0]})\n\n{body}")
        path = _get(type_doc, "path")
        if path:
            paths.append(Path(path))
    return "".join(chunks), paths


def _build_dependency_interfaces(corpus, depends_on_ids):
    type_index = _build_type_owner_index(corpus)
    result = {}
    all_paths = []
    components = _get(corpus, "components", {}) or {}
    for dep_id in depends_on_ids:
        dep_component = components.get(_strip_prefix(dep_id))
        if dep_component is None:
            continue
        interface_text, interface_paths = _build_plain_interface(dep_component)
        extra_text, extra_paths = _resolve_referenced_types(
            dep_component, interface_text, type_index, corpus
        )
        result[dep_id] = interface_text + extra_text
        all_paths.extend(interface_paths)
        all_paths.extend(extra_paths)
    return result, all_paths


def _dependency_context(graph, dep_id: str) -> str:
    row = graph.execute(
        "SELECT purpose FROM component_context WHERE component_id = ?", [dep_id]
    ).fetchone()
    if not row:
        return ""
    return (row[0] or "").strip()


def _dependency_usage_card(repo_root: Path, dep_slug: str, sealed: bool, source_path) -> str:
    rel_dir = source_path.rstrip("/") if (sealed and source_path) else f"gen/{dep_slug}"
    code_dir = _resolve_code_dir(repo_root, rel_dir)
    if code_dir is None:
        return ""
    module_name = dep_slug.replace("-", "_")
    flat = code_dir / f"{module_name}.py"
    pkg_init = code_dir / module_name / "__init__.py"
    if flat.is_file():
        module_path = flat
    elif pkg_init.is_file():
        module_path = pkg_init
    else:
        return ""
    try:
        module = _load_module_from_path(module_name, module_path)
    except Exception:
        return ""

    members = []
    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if getattr(obj, "__module__", None) != module_name:
            continue
        members.append(name)
    members.sort()

    dir_text = rel_dir if rel_dir.endswith("/") else rel_dir + "/"
    lines = [f"Importable as: `{module_name}` (module path `{dir_text}`)."]
    for name in members:
        obj = getattr(module, name)
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            continue
        doc_lines = (inspect.getdoc(obj) or "").splitlines()
        first_line = doc_lines[0] if doc_lines else ""
        if first_line:
            lines.append(f"- `{name}{sig}` -- {first_line}")
        else:
            lines.append(f"- `{name}{sig}`")
    return "\n".join(lines)


def _read_glossary(corpus):
    glossary_files = sorted(
        (_get(corpus, "glossary_files", []) or []), key=lambda p: Path(p).as_posix()
    )
    paths = [Path(p) for p in glossary_files]
    text = "\n\n".join(_read_text(p) for p in paths)
    return text, paths


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle:
    if mode not in ("cold", "hint"):
        raise ValueError(f"invalid mode: {mode!r}")
    repo_root = Path(repo_root)

    spec_linter, graph_query_engine = _load_tooling(repo_root)
    corpus = spec_linter.load_corpus(repo_root)
    _ensure_lint_clean(spec_linter, repo_root)

    graph = _get(corpus, "graph")
    graph_query_engine.load_views(graph, repo_root)

    slug = _strip_prefix(component_id)
    components = _get(corpus, "components", {}) or {}
    component = components.get(slug)
    if component is None:
        raise ValueError(f"unknown component: {component_id}")

    root_doc = _get(component, "root")
    if root_doc is None:
        raise ValueError(f"component {component_id} has no component.md")
    frontmatter = _get(root_doc, "frontmatter", {}) or {}
    depends_on = list(frontmatter.get("depends_on") or [])
    uses_var = list(frontmatter.get("uses_var") or [])

    hash_paths = set()
    root_path = _get(root_doc, "path")
    if root_path:
        hash_paths.add(Path(root_path))

    constraints_doc = _get(component, "constraints")
    constraints_text = ""
    if constraints_doc:
        constraints_text = (_get(constraints_doc, "body", "") or "").strip()
        path = _get(constraints_doc, "path")
        if path:
            hash_paths.add(Path(path))

    requirements = _get(component, "requirements", {}) or {}
    req_bodies = []
    for req_id in sorted(requirements.keys()):
        doc = requirements[req_id]
        req_bodies.append((_get(doc, "body", "") or "").strip())
        path = _get(doc, "path")
        if path:
            hash_paths.add(Path(path))

    body = _get(root_doc, "body", "") or ""
    stripped_body = _strip_sections(body, {"Rationale", "Open questions", "Change log"}).strip()
    spec_text = "\n\n".join(p for p in [stripped_body] + req_bodies if p)

    interface_text, interface_doc_paths = _build_target_interface(component, repo_root)
    hash_paths.update(interface_doc_paths)

    dependency_interfaces, dep_interface_paths = _build_dependency_interfaces(corpus, depends_on)
    hash_paths.update(dep_interface_paths)

    dependency_context = {}
    dependency_usage = {}
    for dep_id in depends_on:
        dep_slug = _strip_prefix(dep_id)
        dep_component = components.get(dep_slug)
        if dep_component is None:
            continue
        dep_root = _get(dep_component, "root")
        dep_frontmatter = (_get(dep_root, "frontmatter", {}) or {}) if dep_root else {}
        if dep_root:
            dep_root_path = _get(dep_root, "path")
            if dep_root_path:
                hash_paths.add(Path(dep_root_path))
        dep_sealed = bool(dep_frontmatter.get("sealed"))
        dep_source_path = dep_frontmatter.get("source_path")

        dependency_context[dep_id] = _dependency_context(graph, dep_id)
        dependency_usage[dep_id] = _dependency_usage_card(
            repo_root, dep_slug, dep_sealed, dep_source_path
        )

        code_dir_rel = (
            dep_source_path.rstrip("/") if (dep_sealed and dep_source_path) else f"gen/{dep_slug}"
        )
        code_dir = _resolve_code_dir(repo_root, code_dir_rel)
        if code_dir:
            hash_paths.update(_walk_code_dir(code_dir))

    vars_dict = {}
    id_index = _get(corpus, "id_index", {}) or {}
    for var_id in uses_var:
        var_doc = id_index.get(var_id)
        if var_doc is None:
            continue
        path = _get(var_doc, "path")
        if path:
            vars_dict[var_id] = _read_text(Path(path))
            hash_paths.add(Path(path))

    glossary_text, glossary_paths = _read_glossary(corpus)
    hash_paths.update(glossary_paths)

    hint_code = None
    if mode == "hint":
        gen_dir = repo_root / "gen" / slug
        hint_code = {}
        gen_files = _walk_code_dir(gen_dir)
        for file_path in gen_files:
            rel = file_path.relative_to(gen_dir).as_posix()
            hint_code[rel] = _read_text(file_path)
        hash_paths.update(gen_files)

    existing_paths = {p for p in hash_paths if p.is_file()}
    spec_bundle_hash = _compute_hash(mode, existing_paths, repo_root)

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        spec=spec_text,
        interface=interface_text,
        constraints=constraints_text,
        dependency_interfaces=dependency_interfaces,
        dependency_context=dependency_context,
        dependency_usage=dependency_usage,
        vars=vars_dict,
        glossary=glossary_text,
        hint_code=hint_code,
    )


def _extract_covers(body: str) -> str:
    match = re.search(r"^Covers:\s*(\S+)", body, re.MULTILINE)
    return match.group(1) if match else ""


def assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle:
    repo_root = Path(repo_root)

    spec_linter, graph_query_engine = _load_tooling(repo_root)
    corpus = spec_linter.load_corpus(repo_root)
    _ensure_lint_clean(spec_linter, repo_root)

    graph = _get(corpus, "graph")
    graph_query_engine.load_views(graph, repo_root)

    slug = _strip_prefix(component_id)
    components = _get(corpus, "components", {}) or {}
    component = components.get(slug)
    if component is None:
        raise ValueError(f"unknown component: {component_id}")

    acceptance = _get(component, "acceptance", {}) or {}
    crit_doc = acceptance.get(criterion_id)
    if crit_doc is None:
        raise ValueError(f"unknown criterion: {criterion_id}")

    criterion_text = _get(crit_doc, "body", "") or ""
    covers = _extract_covers(criterion_text)

    requirements = _get(component, "requirements", {}) or {}
    req_doc = requirements.get(covers)
    requirement_text = (_get(req_doc, "body", "") or "") if req_doc else ""

    interface_text, _ = _build_target_interface(component, repo_root)

    root_doc = _get(component, "root")
    frontmatter = (_get(root_doc, "frontmatter", {}) or {}) if root_doc else {}
    depends_on = list(frontmatter.get("depends_on") or [])

    dependency_interfaces, _ = _build_dependency_interfaces(corpus, depends_on)

    glossary_text, _ = _read_glossary(corpus)

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


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs assemble", add_help=True)
    parser.add_argument("component_id")
    parser.add_argument("--mode", choices=["cold", "hint"], default="cold")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    repo_root = Path(args.repo_root)

    try:
        bundle = assemble(args.component_id, repo_root, mode=args.mode)
    except PreconditionFailure as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(asdict(bundle), indent=2))
    else:
        print(f"component: {bundle.component_id}")
        print(f"hash: {bundle.spec_bundle_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))