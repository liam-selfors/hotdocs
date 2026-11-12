"""Size checker: measures each component of a spec corpus against the
size caps of SPEC_GUIDELINES.md section 4 and reports findings.

Library contract: ``check(repo_root: Path) -> list[dict]``.
"""

import importlib.util
import re
import sys
from pathlib import Path, PurePosixPath

# (dimension, warn above, hard fail above or None for warn-only)
_DIMENSIONS = (
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

_SIGNATURE = re.compile(r"^\w+\(.*\)\s*(->|:)")
_PURPOSE_HEADING = re.compile(r"^##\s+Purpose\s*$")
_H2 = re.compile(r"^##\s")


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_corpus_loader(repo_root):
    base = Path(repo_root) / "gen" / "corpus-loader"
    if not base.is_dir():
        base = _tool_root() / "gen" / "corpus-loader"
    flat = base / "corpus_loader.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location("corpus_loader", flat)
    else:
        init = base / "corpus_loader" / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            "corpus_loader", init, submodule_search_locations=[str(init.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["corpus_loader"] = module
    spec.loader.exec_module(module)
    return module


def _severity(value, warn, fail):
    if fail is not None and value > fail:
        return "fail", fail
    if value > warn:
        return "warn", warn
    return None, None


def _finding(rule_id, severity, file, line, message):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "file": file,
        "line": line,
        "message": message,
    }


def _doc_words(graph):
    cur = graph.execute("SELECT * FROM component_size")
    cols = [d[0] for d in cur.description]
    records = [dict(zip(cols, row)) for row in cur.fetchall()]
    return {
        value: rec["word_count"]
        for rec in records
        for key, value in rec.items()
        if key != "word_count"
    }


def _as_list(value):
    if isinstance(value, list):
        return value
    return [value] if value else []


def _depends_on(component):
    frontmatter = _get(_get(component, "root"), "frontmatter") or {}
    return _as_list(_get(frontmatter, "depends_on"))


def _generated_loc(gen_dir):
    return sum(
        1
        for py in sorted(gen_dir.rglob("*.py"))
        for line in py.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def _first_fence(doc):
    body = _get(doc, "body") or ""
    block, inside = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            if inside:
                break
            inside = True
        elif inside:
            block.append(line)
    return "\n".join(block).replace("\\\n", "").split("\n")


def _interface_surface(component):
    cli = sum(1 for line in _first_fence(_get(component, "interface_cli")) if line.strip())
    lib = sum(
        1
        for line in _first_fence(_get(component, "interface_library"))
        if _SIGNATURE.match(line)
    )
    data = len(_get(component, "interface_data") or {})
    return cli + lib + data


def _purpose(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if _PURPOSE_HEADING.match(line):
            end = next(
                (j for j in range(i + 1, len(lines)) if _H2.match(lines[j])),
                len(lines),
            )
            return i + 1, len("\n".join(lines[i + 1:end]).split())
    return None


def check(repo_root):
    repo_root = Path(repo_root)
    loader = _load_corpus_loader(repo_root)
    corpus = loader.load_corpus(repo_root)
    components = _get(corpus, "components") or {}
    doc_words = _doc_words(_get(corpus, "graph"))
    deps = {name: _depends_on(components[name]) for name in components}

    findings = []
    for name in sorted(components):
        comp = components[name]
        root = _get(comp, "root")
        comp_id = _get(root, "doc_id")
        comp_file = f"specs/components/{name}/component.md"

        values = {
            "generated_code_loc": _generated_loc(repo_root / "gen" / name),
            "component_doc_words": int(doc_words.get(name) or 0),
            "requirement_count": len(_get(comp, "requirements") or {}),
            "interface_surface": _interface_surface(comp),
            "fan_out": len(deps[name]),
            "fan_in": sum(1 for d in deps.values() if comp_id in d),
            "guarantee_count": len(_get(comp, "interface_guarantees") or {}),
            "acceptance_count": len(_get(comp, "acceptance") or {}),
        }

        over_warn = []
        for dim, warn, fail in _DIMENSIONS:
            value = values[dim]
            severity, limit = _severity(value, warn, fail)
            if severity is not None:
                over_warn.append(dim)
                findings.append(
                    _finding(
                        "R-SIZE-001",
                        severity,
                        comp_file,
                        1,
                        f"{dim} for component '{name}' is {value}, above the "
                        f"{severity} threshold of {limit} (SPEC_GUIDELINES.md §4)",
                    )
                )

        if len(over_warn) >= 2:
            named = ", ".join(f"{dim}={values[dim]}" for dim in over_warn)
            findings.append(
                _finding(
                    "R-SIZE-002",
                    "warn",
                    comp_file,
                    1,
                    f"component '{name}' has several size-cap dimensions over "
                    f"their warn threshold at once ({named}): a decomposition "
                    f"signal, see SPEC_GUIDELINES.md §4's decomposition-signal "
                    f"guidance",
                )
            )

        if root is not None:
            purpose = _purpose(_get(root, "path"))
            if purpose is not None:
                line, words = purpose
                severity, limit = _severity(words, _PURPOSE_WARN, _PURPOSE_FAIL)
                if severity is not None:
                    findings.append(
                        _finding(
                            "R-SIZE-004",
                            severity,
                            comp_file,
                            line,
                            f"Purpose section of component '{name}' has {words} "
                            f"words, above the {severity} threshold of {limit} "
                            f"(SPEC_GUIDELINES.md §3.4, one paragraph)",
                        )
                    )

        units = list((_get(comp, "requirements") or {}).values()) + list(
            (_get(comp, "acceptance") or {}).values()
        )
        for doc in units:
            words = len((_get(doc, "body") or "").split())
            severity, limit = _severity(words, _FILE_WARN, _FILE_FAIL)
            if severity is not None:
                rel = _get(doc, "rel_path")
                findings.append(
                    _finding(
                        "R-SIZE-003",
                        severity,
                        rel,
                        1,
                        f"{rel} has {words} words, above the per-file {severity} "
                        f"threshold of {limit} (SPEC_GUIDELINES.md §4)",
                    )
                )

    findings.sort(key=lambda f: PurePosixPath(f["file"]).parts)
    return findings