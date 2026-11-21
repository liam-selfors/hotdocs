"""Size checker: SPEC_GUIDELINES.md §4 size caps as linter findings."""

import importlib.util
import re
import sys
from pathlib import Path

_DIMENSIONS = [
    ("generated_code_loc", 800, 1500),
    ("component_doc_words", 2000, 4000),
    ("requirement_count", 20, 40),
    ("interface_surface", 10, 20),
    ("fan_out", 7, None),
    ("fan_in", 10, None),
    ("guarantee_count", 5, 10),
    ("acceptance_count", 25, 50),
]

_FILE_WARN, _FILE_FAIL = 250, 500
_PURPOSE_WARN, _PURPOSE_FAIL = 80, 150

_LIBRARY_LINE = re.compile(r"^\w+\(.*\)\s*(->|:)")
_PURPOSE_HEADING = re.compile(r"^##\s+Purpose\b")
_H2 = re.compile(r"^##\s")


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_dependency(repo_root, slug, module_name):
    dep_dir = Path(repo_root) / "gen" / slug
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / slug
    flat = dep_dir / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = dep_dir / module_name
        spec = importlib.util.spec_from_file_location(
            module_name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _first_fenced_block(text):
    inside = False
    block = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if inside:
                return block
            inside = True
            continue
        if inside:
            block.append(line)
    return block


def _join_continuations(lines):
    out = []
    buf = None
    for line in lines:
        if buf is not None:
            line = buf + line
            buf = None
        if line.endswith("\\"):
            buf = line[:-1]
        else:
            out.append(line)
    if buf is not None:
        out.append(buf)
    return out


def _depends_on(root):
    deps = _get(_get(root, "frontmatter") or {}, "depends_on") or []
    if isinstance(deps, str):
        deps = [deps]
    return list(deps)


def _component_id(name, root):
    doc_id = _get(root, "doc_id")
    return doc_id if doc_id else f"comp-{name}"


def _generated_code_loc(repo_root, name):
    count = 0
    for path in sorted((Path(repo_root) / "gen" / name).rglob("*.py")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    return count


def _interface_surface(component):
    count = 0
    cli = _get(component, "interface_cli")
    if cli is not None:
        for line in _join_continuations(_first_fenced_block(_get(cli, "body") or "")):
            if line.strip():
                count += 1
    library = _get(component, "interface_library")
    if library is not None:
        for line in _join_continuations(_first_fenced_block(_get(library, "body") or "")):
            if _LIBRARY_LINE.match(line):
                count += 1
    count += len(_get(component, "interface_data") or {})
    return count


def _component_doc_words(graph):
    cursor = graph.execute("SELECT * FROM component_size")
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    wc_index = columns.index("word_count")
    key_index = next(i for i, c in enumerate(columns) if c != "word_count")
    return {str(row[key_index]): row[wc_index] for row in rows}


def _severity(value, warn, fail):
    if fail is not None and value > fail:
        return "fail"
    if value > warn:
        return "warn"
    return None


def _finding(rule_id, severity, file, line, message):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "file": file,
        "line": line,
        "message": message,
    }


def _purpose_findings(root, rel):
    path = _get(root, "path")
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if _PURPOSE_HEADING.match(line):
            section = []
            for following in lines[i + 1:]:
                if _H2.match(following):
                    break
                section.append(following)
            words = len("\n".join(section).split())
            sev = _severity(words, _PURPOSE_WARN, _PURPOSE_FAIL)
            if sev is None:
                return []
            threshold = _PURPOSE_FAIL if sev == "fail" else _PURPOSE_WARN
            return [_finding(
                "R-SIZE-004", sev, rel, i + 1,
                f"Purpose section has {words} words, above the {sev} "
                f"threshold of {threshold} (SPEC_GUIDELINES.md §3.4: one paragraph)",
            )]
    return []


def check(repo_root: Path) -> list:
    repo_root = Path(repo_root)
    corpus_loader = _load_dependency(repo_root, "corpus-loader", "corpus_loader")
    corpus = corpus_loader.load_corpus(repo_root)

    docs = list(_get(corpus, "docs") or [])
    components = _get(corpus, "components") or {}
    doc_words = _component_doc_words(_get(corpus, "graph"))

    ids_depended_on = []
    for comp in components.values():
        ids_depended_on.extend(_depends_on(_get(comp, "root")))

    findings = []

    for name in sorted(components):
        comp = components[name]
        root = _get(comp, "root")
        rel = _get(root, "rel_path") or f"specs/components/{name}/component.md"
        comp_id = _component_id(name, root)
        words = doc_words.get(name, doc_words.get(comp_id, 0))
        values = {
            "generated_code_loc": _generated_code_loc(repo_root, name),
            "component_doc_words": words,
            "requirement_count": len(_get(comp, "requirements") or {}),
            "interface_surface": _interface_surface(comp),
            "fan_out": len(_depends_on(root)),
            "fan_in": ids_depended_on.count(comp_id),
            "guarantee_count": len(_get(comp, "interface_guarantees") or {}),
            "acceptance_count": len(_get(comp, "acceptance") or {}),
        }
        over_warn = []
        for dim, warn, fail in _DIMENSIONS:
            value = values[dim]
            sev = _severity(value, warn, fail)
            if sev is None:
                continue
            over_warn.append((dim, value))
            threshold = fail if sev == "fail" else warn
            findings.append(_finding(
                "R-SIZE-001", sev, rel, 1,
                f"{name}: {dim} is {value}, above the {sev} threshold of {threshold}",
            ))
        if len(over_warn) >= 2:
            listed = ", ".join(f"{dim}={value}" for dim, value in over_warn)
            findings.append(_finding(
                "R-SIZE-002", "warn", rel, 1,
                f"{name}: {len(over_warn)} size-cap dimensions over their warn "
                f"thresholds at once ({listed}); see SPEC_GUIDELINES.md §4's "
                f"decomposition-signal guidance",
            ))
        if root is not None:
            findings.extend(_purpose_findings(root, rel))

    for doc in docs:
        if _get(doc, "doc_type") not in ("component-requirement", "component-acceptance"):
            continue
        words = len((_get(doc, "body") or "").split())
        sev = _severity(words, _FILE_WARN, _FILE_FAIL)
        if sev is None:
            continue
        threshold = _FILE_FAIL if sev == "fail" else _FILE_WARN
        rel = _get(doc, "rel_path")
        findings.append(_finding(
            "R-SIZE-003", sev, rel, 1,
            f"{rel} has {words} words, above the per-file {sev} threshold of {threshold}",
        ))

    order = {_get(doc, "rel_path"): i for i, doc in enumerate(docs)}
    findings.sort(key=lambda f: (order.get(f["file"], len(order)), f["file"]))
    return findings
