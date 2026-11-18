"""Spec Bundle Assembler: builds a component's generation input (SpecBundle)
and the narrower CriterionBundle used by test-author."""

import dataclasses
import hashlib
import importlib.util
import inspect
import json
import re
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

__all__ = [
    "PreconditionFailure",
    "SpecBundle",
    "CriterionBundle",
    "assemble",
    "assemble_criterion",
    "main",
]

USAGE = (
    "usage: hotdocs assemble <component-id> [--mode=cold|hint] "
    "[--repo-root=<dir>] [--format=json|text]"
)

_DROPPED_SECTIONS = {"Rationale", "Open questions", "Change log"}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKTICKED = re.compile(r"`([^`]+)`")


class PreconditionFailure(Exception):
    """The corpus does not satisfy assembly's preconditions."""


class _ReadOnlyMapping:
    def keys(self):
        return [f.name for f in fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(fields(self))

    def __contains__(self, key):
        return key in self.keys()

    def __getitem__(self, key):
        if key in self:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self:
            return getattr(self, key)
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
    hint_code: object = None


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


# ---------------------------------------------------------------- helpers


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _module_file(directory, module_name):
    flat = directory / f"{module_name}.py"
    if flat.is_file():
        return flat
    return directory / module_name / "__init__.py"


def _load_module(module_name, path):
    locations = [str(path.parent)] if path.name == "__init__.py" else None
    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep(repo_root, slug, module_name):
    directory = repo_root / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    return _load_module(module_name, _module_file(directory, module_name))


def _checked_corpus(repo_root):
    linter = _load_dep(repo_root, "spec-linter", "spec_linter")
    gqe = _load_dep(repo_root, "graph-query-engine", "graph_query_engine")
    report = linter.lint(None, repo_root)
    failures = _get(report, "hard_failures")
    if failures:
        raise PreconditionFailure(
            f"corpus is not lint-clean: {failures} hard failure(s)"
        )
    corpus = linter.load_corpus(repo_root)
    gqe.load_views(_get(corpus, "graph"), repo_root)
    return corpus


def _join(texts):
    stripped = [t.strip() for t in texts]
    return "\n\n".join(t for t in stripped if t)


def _sorted_docs(mapping):
    return [mapping[k] for k in sorted(mapping)]


def _frontmatter(comp):
    return _get(_get(comp, "root"), "frontmatter")


def _components_by_id(corpus):
    return {
        _get(_frontmatter(c), "id"): c for c in _get(corpus, "components").values()
    }


def _strip_sections(body):
    kept = []
    skipping = False
    for line in body.split("\n"):
        if line.startswith("## "):
            skipping = line[3:].strip() in _DROPPED_SECTIONS
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


def _interface_docs(comp):
    docs = []
    for key in ("interface_cli", "interface_library"):
        doc = _get(comp, key)
        if doc is not None:
            docs.append(doc)
    docs.extend(_sorted_docs(_get(comp, "interface_data")))
    docs.extend(_sorted_docs(_get(comp, "interface_guarantees")))
    return docs


def _implements_paths(comp):
    body = _get(_get(comp, "interface_library"), "body", "")
    paths = []
    for line in body.split("\n"):
        if line.startswith("Implements:"):
            paths.extend(_BACKTICKED.findall(line))
    return paths


def _interface_text(repo_root, comp, hashed):
    parts = [_get(d, "body") for d in _interface_docs(comp)]
    for rel in _implements_paths(comp):
        path = repo_root / rel
        if not path.is_file():
            raise PreconditionFailure(f"Implements: {rel} does not exist")
        parts.append(f"## Implements: {rel}\n\n{path.read_text(encoding='utf-8')}")
        hashed.add(rel)
    return _join(parts)


def _dependency_interfaces(corpus, comp, by_id, hashed):
    owners = {}
    for c in _get(corpus, "components").values():
        owner_id = _get(_frontmatter(c), "id")
        for stem, doc in _get(c, "interface_data").items():
            owners.setdefault(stem, []).append((owner_id, doc))
    result = {}
    for dep_id in _get(_frontmatter(comp), "depends_on", []):
        dep = by_id[dep_id]
        docs = _interface_docs(dep)
        parts = [_get(d, "body") for d in docs]
        identifiers = set()
        for doc in docs:
            identifiers.update(_IDENT.findall(_get(doc, "body")))
        for name in sorted(identifiers - set(_get(dep, "interface_data"))):
            found = owners.get(name, [])
            if len(found) == 1:
                owner_id, doc = found[0]
                parts.append(f"## Type: {name} (owned by {owner_id})\n\n{_get(doc, 'body')}")
                hashed.add(_get(doc, "rel_path"))
        result[dep_id] = _join(parts)
    return result


def _md_files(repo_root, rel_dir):
    return sorted(
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / rel_dir).rglob("*.md")
        if p.is_file()
    )


def _code_files(repo_root, rel_dir):
    base = repo_root / rel_dir
    return sorted(
        p.relative_to(repo_root).as_posix()
        for p in base.rglob("*")
        if p.is_file()
        and not p.name.startswith(".")
        and "__pycache__" not in p.relative_to(base).parts
    )


def _code_dir(comp):
    fm = _frontmatter(comp)
    if _get(fm, "sealed"):
        return str(_get(fm, "source_path")).rstrip("/") + "/"
    return f"gen/{_get(comp, 'name')}/"


def _usage_card(repo_root, comp, code_rel):
    module_name = _get(comp, "name").replace("-", "_")
    path = _module_file(repo_root / code_rel, module_name)
    if not path.is_file():
        return ""
    module = _load_module(module_name, path)
    lines = [f"Importable as: `{module_name}` (module path `{code_rel}`)."]
    for name in sorted(vars(module)):
        obj = getattr(module, name)
        if name.startswith("_"):
            continue
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        try:
            signature = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        line = f"- `{name}{signature}`"
        first = (obj.__doc__ or "").strip().split("\n")[0]
        if first:
            line += f" -- {first}"
        lines.append(line)
    return "\n".join(lines)


def _glossary(repo_root):
    return (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------- library


def assemble(component_id, repo_root, mode="cold"):
    """Assemble the SpecBundle for `component_id` from the corpus at `repo_root`."""
    repo_root = Path(repo_root)
    corpus = _checked_corpus(repo_root)
    graph = _get(corpus, "graph")
    by_id = _components_by_id(corpus)
    comp = by_id[component_id]
    root = _get(comp, "root")
    fm = _frontmatter(comp)
    name = _get(comp, "name")
    base = f"specs/components/{name}"

    hashed = {f"{base}/component.md", f"{base}/constraints.md", "specs/glossary.md"}
    hashed.update(_md_files(repo_root, f"{base}/requirements"))
    hashed.update(_md_files(repo_root, f"{base}/interface"))

    spec = _join(
        [_strip_sections(_get(root, "body"))]
        + [_get(d, "body") for d in _sorted_docs(_get(comp, "requirements"))]
    )
    interface = _interface_text(repo_root, comp, hashed)
    constraints = _get(_get(comp, "constraints"), "body", "").strip()
    dependency_interfaces = _dependency_interfaces(corpus, comp, by_id, hashed)

    dependency_context = {}
    dependency_usage = {}
    for dep_id in _get(fm, "depends_on", []):
        dep = by_id[dep_id]
        dep_name = _get(dep, "name")
        code_rel = _code_dir(dep)
        hashed.add(f"specs/components/{dep_name}/component.md")
        hashed.update(_md_files(repo_root, f"specs/components/{dep_name}/interface"))
        hashed.update(_code_files(repo_root, code_rel))
        row = graph.execute(
            "SELECT purpose FROM component_context WHERE component_id = ?", [dep_id]
        ).fetchone()
        dependency_context[dep_id] = row[0].strip()
        dependency_usage[dep_id] = _usage_card(repo_root, dep, code_rel)

    var_docs = {
        _get(d, "doc_id"): d
        for d in _get(corpus, "docs")
        if _get(d, "doc_type") == "var"
    }
    bundle_vars = {}
    for var_id in _get(fm, "uses_var", []):
        doc = var_docs[var_id]
        bundle_vars[var_id] = _get(doc, "body").strip()
        hashed.add(_get(doc, "rel_path"))

    hint_code = None
    if mode == "hint":
        prefix = f"gen/{name}/"
        files = _code_files(repo_root, prefix)
        hint_code = {
            rel[len(prefix):]: (repo_root / rel).read_text(encoding="utf-8", errors="replace")
            for rel in files
        }
        hashed.update(files)

    digest = hashlib.sha256(mode.encode("utf-8") + b"\0")
    for rel in sorted(hashed):
        path = repo_root / rel
        if path.is_file():
            digest.update(rel.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest.hexdigest(),
        spec=spec,
        interface=interface,
        constraints=constraints,
        dependency_interfaces=dependency_interfaces,
        dependency_context=dependency_context,
        dependency_usage=dependency_usage,
        vars=bundle_vars,
        glossary=_glossary(repo_root),
        hint_code=hint_code,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    """Assemble the CriterionBundle for one acceptance criterion."""
    repo_root = Path(repo_root)
    corpus = _checked_corpus(repo_root)
    graph = _get(corpus, "graph")
    by_id = _components_by_id(corpus)
    comp = by_id[component_id]
    criterion = _get(comp, "acceptance")[criterion_id]
    covers = graph.execute(
        "SELECT target_id FROM edges WHERE source_id = ? AND edge_type = 'covers' "
        "ORDER BY target_id",
        [criterion_id],
    ).fetchone()[0]
    requirement = _get(comp, "requirements")[covers]
    unused = set()
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=_get(criterion, "body").strip(),
        requirement_text=_get(requirement, "body").strip(),
        interface=_interface_text(repo_root, comp, unused),
        glossary=_glossary(repo_root),
        dependency_interfaces=_dependency_interfaces(corpus, comp, by_id, unused),
    )


# ---------------------------------------------------------------- CLI


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    options = {"--mode": "cold", "--repo-root": None, "--format": "text"}
    positional = []
    i = 0
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in options:
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} requires a value")
                i += 1
                value = argv[i]
            options[name] = value
        elif token.startswith("-"):
            return _usage_error(f"unknown argument {token}")
        else:
            positional.append(token)
        i += 1

    if not positional:
        return _usage_error("missing <component-id>")
    if len(positional) > 1:
        return _usage_error(f"unexpected argument {positional[1]}")
    mode = options["--mode"]
    if mode not in ("cold", "hint"):
        return _usage_error(f"invalid --mode {mode!r}")
    fmt = options["--format"]
    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format {fmt!r}")
    repo_root = Path(options["--repo-root"] or Path.cwd())
    component_id = positional[0]

    try:
        bundle = assemble(component_id, repo_root, mode)
    except PreconditionFailure as exc:
        print(f"precondition failure: {exc}", file=sys.stderr)
        return 1
    except KeyError:
        return _usage_error(f"unknown component id {component_id}")

    if fmt == "json":
        print(json.dumps(dataclasses.asdict(bundle), indent=2))
    else:
        print(f"component_id: {bundle.component_id}")
        print(f"spec_bundle_hash: {bundle.spec_bundle_hash}")
        print(f"mode: {mode}")
        print(f"dependencies: {', '.join(bundle.dependency_interfaces)}")
        print(f"vars: {', '.join(bundle.vars)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
