"""size-checker: measures each component against SPEC_GUIDELINES.md §4's
size caps and reports each cap exceeded as a linter finding."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path, PurePosixPath

_GUIDE = "SPEC_GUIDELINES.md §4"

# (dimension, warn above, fail above or None for warn-only)
_CAPS = (
    ("generated_code_loc", 800, 1500),
    ("component_doc_words", 2000, 4000),
    ("requirement_count", 20, 40),
    ("interface_surface", 10, 20),
    ("fan_out", 7, None),
    ("fan_in", 10, None),
    ("guarantee_count", 5, 10),
    ("acceptance_count", 25, 50),
)

_FILE_WARN, _FILE_FAIL = 250, 500
_PURPOSE_WARN, _PURPOSE_FAIL = 80, 150

_LIBRARY_SIG = re.compile(r"^\w+\(.*\)\s*(->|:)")
_PURPOSE_HEADING = re.compile(r"^##\s+Purpose\s*$")
_LEVEL2_HEADING = re.compile(r"^##(?!#)")


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_corpus_loader(repo_root: Path):
    rel = Path("gen") / "corpus-loader"
    dep_dir = Path(repo_root) / rel
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / rel
    flat = dep_dir / "corpus_loader.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location("corpus_loader", flat)
    else:
        spec = importlib.util.spec_from_file_location(
            "corpus_loader",
            dep_dir / "corpus_loader" / "__init__.py",
            submodule_search_locations=[str(dep_dir / "corpus_loader")],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["corpus_loader"] = module
    spec.loader.exec_module(module)
    return module


def _as_list(value):
    if isinstance(value, list):
        return value
    return [value] if value else []


def _fenced_block(text: str) -> list:
    inside = False
    out = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if inside:
                return out
            inside = True
            continue
        if inside:
            out.append(line)
    return out


def _join_continuations(lines: list) -> list:
    out = []
    buf = ""
    for line in lines:
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        out.append(buf + line)
        buf = ""
    return out


def _interface_surface(comp) -> int:
    cli_body = _get(_get(comp, "interface_cli"), "body") or ""
    lib_body = _get(_get(comp, "interface_library"), "body") or ""
    cli = sum(1 for line in _join_continuations(_fenced_block(cli_body)) if line.strip())
    lib = sum(
        1
        for line in _join_continuations(_fenced_block(lib_body))
        if _LIBRARY_SIG.match(line)
    )
    data = len(_get(comp, "interface_data") or {})
    return cli + lib + data


def _generated_code_loc(repo_root: Path, name: str) -> int:
    total = 0
    for path in sorted((Path(repo_root) / "gen" / name).rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                total += 1
    return total


def _doc_words_by_component(graph) -> dict:
    cur = graph.execute("SELECT * FROM component_size")
    cols = [d[0] for d in cur.description]
    w = cols.index("word_count")
    k = next(i for i, c in enumerate(cols) if c != "word_count")
    return {row[k]: int(row[w] or 0) for row in cur.fetchall()}


def _severity(value: int, warn: int, fail):
    if fail is not None and value > fail:
        return "fail"
    if value > warn:
        return "warn"
    return None


def _finding(rule_id, severity, file, line, message) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "file": file,
        "line": line,
        "message": message,
    }


def _purpose_findings(root) -> list:
    body = _get(root, "body") or ""
    lines = body.split("\n")
    start = next((i for i, line in enumerate(lines) if _PURPOSE_HEADING.match(line)), None)
    if start is None:
        return []
    section = []
    for line in lines[start + 1:]:
        if _LEVEL2_HEADING.match(line):
            break
        section.append(line)
    words = len("\n".join(section).split())
    severity = _severity(words, _PURPOSE_WARN, _PURPOSE_FAIL)
    if severity is None:
        return []
    text = Path(_get(root, "path")).read_text(encoding="utf-8")
    offset = len(text.splitlines()) - len(lines)
    threshold = _PURPOSE_FAIL if severity == "fail" else _PURPOSE_WARN
    return [
        _finding(
            "R-SIZE-004",
            severity,
            _get(root, "rel_path"),
            offset + start + 1,
            f"Purpose section has {words} words, above the {severity} "
            f"threshold of {threshold} ({_GUIDE}; §3.4's one-paragraph rule)",
        )
    ]


def check(repo_root: Path) -> list:
    loader = _load_corpus_loader(repo_root)
    corpus = loader.load_corpus(repo_root)

    components = _get(corpus, "components") or {}
    words_by_comp = _doc_words_by_component(_get(corpus, "graph"))

    ids = {}
    deps = {}
    for name, comp in components.items():
        root = _get(comp, "root")
        fm = _get(root, "frontmatter") or {}
        ids[name] = _get(root, "doc_id")
        deps[name] = _as_list(_get(fm, "depends_on"))

    findings = []
    for name, comp in components.items():
        root = _get(comp, "root")
        file = _get(root, "rel_path") or f"specs/components/{name}/component.md"
        values = {
            "generated_code_loc": _generated_code_loc(repo_root, name),
            "component_doc_words": words_by_comp.get(name, 0),
            "requirement_count": len(_get(comp, "requirements") or {}),
            "interface_surface": _interface_surface(comp),
            "fan_out": len(deps[name]),
            "fan_in": sum(1 for other in deps.values() if ids[name] in other),
            "guarantee_count": len(_get(comp, "interface_guarantees") or {}),
            "acceptance_count": len(_get(comp, "acceptance") or {}),
        }
        over_warn = []
        for dim, warn, fail in _CAPS:
            value = values[dim]
            severity = _severity(value, warn, fail)
            if severity is None:
                continue
            over_warn.append(f"{dim}={value}")
            threshold = fail if severity == "fail" else warn
            findings.append(
                _finding(
                    "R-SIZE-001",
                    severity,
                    file,
                    1,
                    f"component '{name}': {dim} is {value}, above the "
                    f"{severity} threshold of {threshold} ({_GUIDE})",
                )
            )
        if len(over_warn) >= 2:
            findings.append(
                _finding(
                    "R-SIZE-002",
                    "warn",
                    file,
                    1,
                    f"component '{name}' is over the warn threshold on "
                    f"{len(over_warn)} size-cap dimensions at once: "
                    f"{', '.join(over_warn)} -- a decomposition signal; see "
                    f"{_GUIDE}'s decomposition-signal guidance",
                )
            )
        findings.extend(_purpose_findings(root))

    for doc in _get(corpus, "docs") or []:
        if _get(doc, "doc_type") not in ("component-requirement", "component-acceptance"):
            continue
        words = len((_get(doc, "body") or "").split())
        severity = _severity(words, _FILE_WARN, _FILE_FAIL)
        if severity is None:
            continue
        threshold = _FILE_FAIL if severity == "fail" else _FILE_WARN
        rel = _get(doc, "rel_path")
        findings.append(
            _finding(
                "R-SIZE-003",
                severity,
                rel,
                1,
                f"{rel} has {words} words, above the per-file {severity} "
                f"threshold of {threshold} ({_GUIDE})",
            )
        )

    findings.sort(key=lambda f: PurePosixPath(f["file"]))
    return findings
