"""Size checker: measures each spec component against SPEC_GUIDELINES.md §4 size caps."""

import importlib.util
import re
import sys
from pathlib import Path

GUIDE = "SPEC_GUIDELINES.md §4"

# (dimension, warn above, fail above or None for warn-only)
DIMENSIONS = [
    ("generated_code_loc", 800, 1500),
    ("component_doc_words", 2000, 4000),
    ("requirement_count", 20, 40),
    ("interface_surface", 10, 20),
    ("fan_out", 7, None),
    ("fan_in", 10, None),
    ("guarantee_count", 5, 10),
    ("acceptance_count", 25, 50),
]

FILE_WARN, FILE_FAIL = 250, 500
PURPOSE_WARN, PURPOSE_FAIL = 80, 150

_LIB_RE = re.compile(r"^\w+\(.*\)\s*(->|:)")
_PURPOSE_RE = re.compile(r"^##\s+Purpose\s*$")
_H2_RE = re.compile(r"^##\s")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_dependency(repo_root, slug, module_name):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _first_fenced_block(text):
    lines = text.splitlines()
    block = []
    inside = False
    for line in lines:
        if line.strip().startswith("```"):
            if inside:
                return block
            inside = True
            continue
        if inside:
            block.append(line)
    return block


def _join_continuations(lines):
    joined = []
    buf = None
    for line in lines:
        current = line if buf is None else buf + line
        if current.endswith("\\"):
            buf = current[:-1]
        else:
            joined.append(current)
            buf = None
    if buf is not None:
        joined.append(buf)
    return joined


def _generated_code_loc(repo_root, name):
    total = 0
    for py in sorted((Path(repo_root) / "gen" / name).rglob("*.py")):
        for line in py.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                total += 1
    return total


def _interface_surface(component):
    cli_body = _get(_get(component, "interface_cli"), "body", "") or ""
    lib_body = _get(_get(component, "interface_library"), "body", "") or ""
    cli_lines = _join_continuations(_first_fenced_block(cli_body))
    lib_lines = _join_continuations(_first_fenced_block(lib_body))
    count = sum(1 for line in cli_lines if line.strip())
    count += sum(1 for line in lib_lines if _LIB_RE.match(line))
    count += len(_get(component, "interface_data", {}) or {})
    return count


def _component_sizes(graph):
    cur = graph.execute("SELECT * FROM component_size")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    wi = cols.index("word_count")
    ki = next(i for i in range(len(cols)) if i != wi)
    return {str(row[ki]): row[wi] for row in rows}


def _depends_on(root):
    return list(_get(_get(root, "frontmatter", {}) or {}, "depends_on", []) or [])


def _finding(rule_id, severity, file, line, message):
    return {"rule_id": rule_id, "severity": severity, "file": file, "line": line, "message": message}


def _cap_finding(rule_id, label, value, warn, fail, file, line):
    if fail is not None and value > fail:
        return _finding(
            rule_id, "fail", file, line,
            f"{label} is {value}, above the fail threshold of {fail} ({GUIDE})",
        )
    if value > warn:
        return _finding(
            rule_id, "warn", file, line,
            f"{label} is {value}, above the warn threshold of {warn} ({GUIDE})",
        )
    return None


def _purpose(root, comp_file):
    body = _get(root, "body", "") or ""
    lines = body.splitlines()
    start = next((i for i, line in enumerate(lines) if _PURPOSE_RE.match(line)), None)
    if start is None:
        return None
    end = next(
        (i for i in range(start + 1, len(lines)) if _H2_RE.match(lines[i])), len(lines)
    )
    words = len("\n".join(lines[start + 1:end]).split())
    path = _get(root, "path")
    file_lines = Path(path).read_text(encoding="utf-8").splitlines()
    line_no = next(
        (i + 1 for i, line in enumerate(file_lines) if _PURPOSE_RE.match(line)), 1
    )
    return _cap_finding(
        "R-SIZE-004", "Purpose section word count", words,
        PURPOSE_WARN, PURPOSE_FAIL, comp_file, line_no,
    )


def check(repo_root: Path) -> list:
    repo_root = Path(repo_root)
    loader = _load_dependency(repo_root, "corpus-loader", "corpus_loader")
    corpus = loader.load_corpus(repo_root)
    components = _get(corpus, "components", {}) or {}
    sizes = _component_sizes(_get(corpus, "graph"))

    ids = {}
    for name, comp in components.items():
        ids[name] = _get(_get(comp, "root"), "doc_id")
    fan_in = {name: 0 for name in components}
    for name, comp in components.items():
        deps = set(_depends_on(_get(comp, "root")))
        for other in components:
            if ids[other] in deps:
                fan_in[other] += 1

    findings = []
    for name in sorted(components):
        comp = components[name]
        root = _get(comp, "root")
        comp_file = f"specs/components/{name}/component.md"

        values = {
            "generated_code_loc": _generated_code_loc(repo_root, name),
            "component_doc_words": sizes.get(name, sizes.get(f"comp-{name}", 0)),
            "requirement_count": len(_get(comp, "requirements", {}) or {}),
            "interface_surface": _interface_surface(comp),
            "fan_out": len(_depends_on(root)),
            "fan_in": fan_in[name],
            "guarantee_count": len(_get(comp, "interface_guarantees", {}) or {}),
            "acceptance_count": len(_get(comp, "acceptance", {}) or {}),
        }

        over_warn = []
        for dim, warn, fail in DIMENSIONS:
            value = values[dim]
            f = _cap_finding("R-SIZE-001", dim, value, warn, fail, comp_file, 1)
            if f is not None:
                findings.append(f)
                over_warn.append(f"{dim}={value}")

        if len(over_warn) >= 2:
            findings.append(_finding(
                "R-SIZE-002", "warn", comp_file, 1,
                f"{len(over_warn)} size-cap dimensions over their warn threshold at once "
                f"({', '.join(over_warn)}): a decomposition signal, see {GUIDE}'s "
                f"decomposition-signal guidance",
            ))

        p = _purpose(root, comp_file)
        if p is not None:
            findings.append(p)

        units = list((_get(comp, "requirements", {}) or {}).values())
        units += list((_get(comp, "acceptance", {}) or {}).values())
        for doc in units:
            words = len((_get(doc, "body", "") or "").split())
            f = _cap_finding(
                "R-SIZE-003", "file word count", words,
                FILE_WARN, FILE_FAIL, _get(doc, "rel_path"), 1,
            )
            if f is not None:
                findings.append(f)

    return sorted(findings, key=lambda f: f["file"])
