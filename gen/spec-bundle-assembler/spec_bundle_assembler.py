"""Spec Bundle Assembler: builds a component's SpecBundle and CriterionBundle."""

import dataclasses
import hashlib
import importlib.util
import inspect
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = (
    "usage: hotdocs assemble <component-id> [--mode=cold|hint] "
    "[--repo-root=<dir>] [--format=json|text]"
)

_EXCLUDED_SECTIONS = {"Rationale", "Open questions", "Change log"}
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKTICKED = re.compile(r"`([^`]+)`")


class PreconditionFailure(Exception):
    """Raised when a bundle cannot be assembled from the corpus as it stands."""


class UnknownComponentError(LookupError):
    """Raised when the requested component id names no component in the corpus."""


class _ReadOnlyMapping:
    def __getitem__(self, key):
        if key in {f.name for f in dataclasses.fields(self)}:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


@dataclass
class SpecBundle(_ReadOnlyMapping):
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
    hint_code: dict = None


@dataclass
class CriterionBundle(_ReadOnlyMapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)
    testing: str = ""


# --------------------------------------------------------------------------
# helpers


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    for parent in Path(__file__).absolute().parents:
        if parent.name == "gen":
            return parent.parent


def _resolve_dir(repo_root, rel):
    directory = repo_root / rel
    if directory.is_dir():
        return directory
    return _tool_root() / rel


def _find_module(directory, name):
    for candidate in (
        directory / f"{name}.py",
        directory / name / "__init__.py",
        directory / "__init__.py",
    ):
        if candidate.is_file():
            return candidate
    return None


def _exec_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependency(slug, repo_root):
    name = slug.replace("-", "_")
    directory = _resolve_dir(repo_root, f"gen/{slug}")
    return _exec_module(name, _find_module(directory, name))


def _join(parts):
    stripped = [p.strip() for p in parts]
    return "\n\n".join(p for p in stripped if p)


def _read(path):
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _backticked(line):
    return _BACKTICKED.findall(line)


def _named_docs(paths, repo_root):
    docs = []
    for rel in paths:
        path = repo_root / rel
        if not path.is_file():
            raise PreconditionFailure(f"named document does not exist: {rel}")
        docs.append((rel, path.read_text(encoding="utf-8")))
    return docs


def _drop_sections(body):
    kept = []
    skipping = False
    for line in body.splitlines():
        if line.startswith("## "):
            skipping = line[3:].strip() in _EXCLUDED_SECTIONS
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


def _component_dir(repo_root, name):
    return repo_root / "specs" / "components" / name


def _frontmatter(comp):
    return _get(_get(comp, "root"), "frontmatter")


def _interface_parts(comp, comp_dir):
    parts = []
    for key in ("interface_cli", "interface_library"):
        doc = _get(comp, key)
        if doc is not None:
            parts.append(_get(doc, "body"))
    for key in ("interface_data", "interface_guarantees"):
        docs = _get(comp, key)
        for doc_key in sorted(docs):
            parts.append(_get(docs[doc_key], "body"))
    for path in sorted((comp_dir / "interface" / "assets").glob("*.md")):
        parts.append(path.read_text(encoding="utf-8"))
    return parts


def _code_files(directory):
    return [
        p
        for p in sorted(directory.rglob("*"))
        if p.is_file()
        and not p.name.startswith(".")
        and "__pycache__" not in p.relative_to(directory).parts
    ]


def _add_file(files, repo_root, rel):
    path = repo_root / rel
    if path.is_file():
        files[rel] = path.read_bytes()


def _add_md_tree(files, repo_root, rel_dir):
    for path in (repo_root / rel_dir).rglob("*.md"):
        if path.is_file():
            files[path.relative_to(repo_root).as_posix()] = path.read_bytes()


def _add_code_dir(files, repo_root, rel_dir):
    directory = repo_root / rel_dir
    for path in _code_files(directory):
        files[f"{rel_dir}/{path.relative_to(directory).as_posix()}"] = path.read_bytes()


def _hash(mode, files):
    digest = hashlib.sha256(mode.encode("utf-8") + b"\0")
    for rel in sorted(files):
        digest.update(rel.encode("utf-8") + b"\0" + files[rel] + b"\0")
    return "sha256:" + digest.hexdigest()


# --------------------------------------------------------------------------
# assembly steps


def _prepare(component_id, repo_root):
    _load_dependency("graph-query-engine", repo_root)
    linter = _load_dependency("spec-linter", repo_root)
    report = linter.lint(None, repo_root)
    failures = [f for f in _get(report, "findings") if _get(f, "severity") == "fail"]
    if failures:
        raise PreconditionFailure(
            f"corpus is not lint-clean: {len(failures)} hard-fail finding(s)"
        )
    corpus = linter.load_corpus(repo_root)
    components = _get(corpus, "components")
    slug = component_id.removeprefix("comp-")
    if slug not in components:
        raise UnknownComponentError(f"unknown component id: {component_id}")
    return corpus, components, slug, components[slug]


def _adapters(comp, repo_root):
    assets = _get(_frontmatter(comp), "assets") or []
    kinds = sorted({str(item).split(":", 1)[0] for item in assets})
    adapters = []
    for kind in kinds:
        rel = f"gen/kind-{kind}/kind_{kind}.py"
        path = repo_root / rel
        if not path.is_file():
            path = _tool_root() / rel
        if not path.is_file():
            raise PreconditionFailure(f"unknown asset kind: {kind}")
        module = _exec_module(f"kind_{kind}", path)
        adapters.append((kind, rel, path, module.guidance()))
    return adapters


def _target_interface(comp, slug, repo_root):
    base = _join(_interface_parts(comp, _component_dir(repo_root, slug)))
    body = _get(_get(comp, "interface_library"), "body") or ""
    paths = []
    for line in body.splitlines():
        if line.startswith("Implements:"):
            paths.extend(_backticked(line))
    docs = _named_docs(paths, repo_root)
    text = base + "".join(
        f"\n\n## Implements: {rel}\n\n{doc.strip()}" for rel, doc in docs
    )
    return text, paths


def _dependency_ids(comp):
    return sorted(set(_get(_frontmatter(comp), "depends_on") or []))


def _type_owners(components):
    owners = {}
    for name in sorted(components):
        for stem in _get(components[name], "interface_data"):
            owners.setdefault(stem, []).append(name)
    return owners


def _dependency_interface(dep_id, components, owners, repo_root):
    name = dep_id.removeprefix("comp-")
    dep = components[name]
    parts = _interface_parts(dep, _component_dir(repo_root, name))
    own = set(_get(dep, "interface_data"))
    type_parts = []
    type_files = []
    for ident in sorted(set(_IDENTIFIER.findall("\n".join(parts)))):
        found = owners.get(ident, [])
        if ident in own or len(found) != 1:
            continue
        owner = found[0]
        doc = _get(components[owner], "interface_data")[ident]
        type_parts.append(f"## Type: {ident} (owned by comp-{owner})\n\n{_get(doc, 'body').strip()}")
        type_files.append(_get(doc, "rel_path"))
    return _join(parts + type_parts), type_files


def _code_dir_rel(name, comp):
    source_path = _get(_frontmatter(comp), "source_path")
    if source_path:
        return str(source_path).rstrip("/")
    return f"gen/{name}"


def _usage_card(name, comp, repo_root):
    rel = _code_dir_rel(name, comp)
    module_name = name.replace("-", "_")
    module_file = _find_module(_resolve_dir(repo_root, rel), module_name)
    if module_file is None:
        return ""
    module = _exec_module(module_name, module_file)
    lines = [f"Importable as: `{module_name}` (module path `{rel}/`)."]
    for attr in sorted(vars(module)):
        if attr.startswith("_"):
            continue
        obj = getattr(module, attr)
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        owner = obj.__module__
        if owner != module_name and not owner.startswith(module_name + "."):
            continue
        try:
            signature = str(inspect.signature(obj))
        except (TypeError, ValueError):
            continue
        line = f"- `{attr}{signature}`"
        doc = (obj.__doc__ or "").strip()
        if doc:
            line += " -- " + doc.splitlines()[0].strip()
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# public entry points


def assemble(component_id, repo_root, mode="cold"):
    """Assemble the SpecBundle for one component."""
    repo_root = Path(repo_root)
    corpus, components, slug, comp = _prepare(component_id, repo_root)
    adapters = _adapters(comp, repo_root)
    files = {}
    comp_rel = f"specs/components/{slug}"

    root = _get(comp, "root")
    requirements = _get(comp, "requirements")
    spec = _join(
        [_drop_sections(_get(root, "body"))]
        + [_get(requirements[key], "body") for key in sorted(requirements)]
    )
    constraints_doc = _get(comp, "constraints")
    constraints = _join([_get(constraints_doc, "body") or ""])
    _add_file(files, repo_root, f"{comp_rel}/component.md")
    _add_file(files, repo_root, f"{comp_rel}/constraints.md")
    _add_md_tree(files, repo_root, f"{comp_rel}/requirements")
    _add_md_tree(files, repo_root, f"{comp_rel}/interface")

    interface, implements = _target_interface(comp, slug, repo_root)
    for rel in implements:
        _add_file(files, repo_root, rel)
    for kind, rel, path, guide in adapters:
        interface += "\n\n## Asset kind: " + kind + "\n\n" + _get(guide, "generator").strip()
        files[rel] = path.read_bytes()

    owners = _type_owners(components)
    rows = _get(corpus, "graph").execute(
        "SELECT component_id, purpose FROM component_context"
    ).fetchall()
    purposes = {row[0]: row[1] for row in rows}
    dependency_interfaces = {}
    dependency_context = {}
    dependency_usage = {}
    for dep_id in _dependency_ids(comp):
        name = dep_id.removeprefix("comp-")
        dep = components[name]
        text, type_files = _dependency_interface(dep_id, components, owners, repo_root)
        dependency_interfaces[dep_id] = text
        dependency_context[dep_id] = (purposes.get(dep_id) or "").strip()
        dependency_usage[dep_id] = _usage_card(name, dep, repo_root)
        _add_file(files, repo_root, f"specs/components/{name}/component.md")
        _add_md_tree(files, repo_root, f"specs/components/{name}/interface")
        _add_code_dir(files, repo_root, _code_dir_rel(name, dep))
        for rel in type_files:
            _add_file(files, repo_root, rel)

    id_index = _get(corpus, "id_index")
    var_texts = {}
    for var_id in sorted(set(_get(_frontmatter(comp), "uses_var") or [])):
        doc = id_index[var_id]
        raw = Path(_get(doc, "path")).read_bytes()
        var_texts[var_id] = raw.decode("utf-8").strip()
        files[_get(doc, "rel_path")] = raw

    glossary = _read(repo_root / "specs" / "glossary.md").strip()
    _add_file(files, repo_root, "specs/glossary.md")

    hint_code = None
    if mode == "hint":
        code_dir = repo_root / "gen" / slug
        hint_code = {
            p.relative_to(code_dir).as_posix(): p.read_text(encoding="utf-8", errors="replace")
            for p in _code_files(code_dir)
        }
        _add_code_dir(files, repo_root, f"gen/{slug}")

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=_hash(mode, files),
        spec=spec,
        interface=interface,
        constraints=constraints,
        dependency_interfaces=dependency_interfaces,
        dependency_context=dependency_context,
        dependency_usage=dependency_usage,
        vars=var_texts,
        glossary=glossary,
        hint_code=hint_code,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    """Assemble the narrower CriterionBundle for one acceptance criterion."""
    repo_root = Path(repo_root)
    corpus, components, slug, comp = _prepare(component_id, repo_root)
    adapters = _adapters(comp, repo_root)

    criterion = _get(comp, "acceptance")[criterion_id]
    covers = _get(corpus, "graph").execute(
        "SELECT target_id FROM edges WHERE source_id = ? AND edge_type = 'covers' "
        "ORDER BY target_id",
        [criterion_id],
    ).fetchone()[0]
    requirement = _get(comp, "requirements")[covers]

    interface, _ = _target_interface(comp, slug, repo_root)
    owners = _type_owners(components)
    dependency_interfaces = {
        dep_id: _dependency_interface(dep_id, components, owners, repo_root)[0]
        for dep_id in _dependency_ids(comp)
    }

    text = _read(_component_dir(repo_root, slug) / "testing.md")
    first = text.split("\n", 1)[0]
    uses = _named_docs(_backticked(first) if first.startswith("Uses:") else [], repo_root)
    testing = (
        text
        + "".join(f"\n## Uses: {rel}\n\n{doc}" for rel, doc in uses)
        + "".join(
            f"\n## Asset kind: {kind}\n\n{_get(guide, 'test_author').strip()}"
            for kind, _rel, _path, guide in adapters
        )
    )

    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=_get(criterion, "body").strip(),
        requirement_text=_get(requirement, "body").strip(),
        interface=interface,
        glossary=_read(repo_root / "specs" / "glossary.md").strip(),
        dependency_interfaces=dependency_interfaces,
        testing=testing,
    )


# --------------------------------------------------------------------------
# CLI


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    """Run `hotdocs assemble`; returns the exit code."""
    args = sys.argv[1:] if argv is None else list(argv)
    options = {"--mode": "cold", "--repo-root": None, "--format": "text"}
    choices = {"--mode": ("cold", "hint"), "--format": ("json", "text")}
    positional = []
    i = 0
    while i < len(args):
        token = args[i]
        if token.startswith("-"):
            name, eq, value = token.partition("=")
            if name not in options:
                return _usage_error(f"unknown argument: {token}")
            if not eq:
                i += 1
                if i >= len(args):
                    return _usage_error(f"{name} requires a value")
                value = args[i]
            if name in choices and value not in choices[name]:
                return _usage_error(f"invalid value for {name}: {value}")
            options[name] = value
        else:
            positional.append(token)
        i += 1
    if not positional:
        return _usage_error("missing <component-id>")
    if len(positional) > 1:
        return _usage_error(f"unexpected argument: {positional[1]}")

    repo_root = Path(options["--repo-root"]) if options["--repo-root"] else Path.cwd()
    try:
        bundle = assemble(positional[0], repo_root, options["--mode"])
    except UnknownComponentError:
        return _usage_error(f"unknown component id: {positional[0]}")
    except PreconditionFailure as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if options["--format"] == "json":
        print(json.dumps(dataclasses.asdict(bundle), indent=2))
    else:
        print(f"component: {bundle.component_id}")
        print(f"mode: {options['--mode']}")
        print(f"spec_bundle_hash: {bundle.spec_bundle_hash}")
        print(f"dependencies: {', '.join(bundle.dependency_interfaces)}")
    return 0
