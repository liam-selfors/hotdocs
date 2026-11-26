"""Size checker: measures each component against specs/architecture/size-caps.md."""

import importlib.util
import re
import sys
from pathlib import Path

_CAPS_DOC = "specs/architecture/size-caps.md"

# R-SIZE-001's nine dimensions, in order: (warn above, fail above or None).
_THRESHOLDS = [
    ("generated_code_loc", 800, 1500),
    ("generator_words", 8000, 14000),
    ("criterion_words_max", 6000, 12000),
    ("requirement_count", 20, 40),
    ("interface_surface", 10, 20),
    ("fan_out", 7, None),
    ("fan_in", 10, None),
    ("guarantee_count", 5, 10),
    ("acceptance_count", 25, 50),
]

_FILE_WARN, _FILE_FAIL = 250, 500
_PURPOSE_WARN, _PURPOSE_FAIL = 80, 150

_LIB_SIG = re.compile(r"^\w+\(.*\)\s*(->|:)")


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_corpus_loader(repo_root):
    base = Path(repo_root) / "gen" / "corpus-loader"
    if not base.is_dir():
        base = _tool_root() / "gen" / "corpus-loader"
    pkg_init = base / "corpus_loader" / "__init__.py"
    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            "corpus_loader", pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location("corpus_loader", base / "corpus_loader.py")
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
    return {"rule_id": rule_id, "severity": severity, "file": file, "line": line, "message": message}


def _first_fenced_block(text):
    block = []
    inside = False
    for line in text.splitlines():
        if line.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside:
            block.append(line)
    return "\n".join(block).replace("\\\n", "").split("\n")


def _interface_surface(comp):
    count = 0
    cli = _get(comp, "interface_cli")
    if cli is not None:
        count += sum(1 for line in _first_fenced_block(_get(cli, "body")) if line.strip())
    lib = _get(comp, "interface_library")
    if lib is not None:
        count += sum(1 for line in _first_fenced_block(_get(lib, "body")) if _LIB_SIG.match(line))
    count += len(_get(comp, "interface_data"))
    return count


def _generated_loc(repo_root, name):
    total = 0
    for path in sorted((Path(repo_root) / "gen" / name).rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                total += 1
    return total


def _deps(comp):
    root = _get(comp, "root")
    deps = _get(root, "frontmatter").get("depends_on", [])
    return [d for d in deps if d]


def _slug(dep):
    return dep.removeprefix("comp-")


def _purpose(root_doc):
    lines = Path(_get(root_doc, "path")).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.rstrip() == "## Purpose":
            words = 0
            for following in lines[i + 1:]:
                if re.match(r"^##\s", following):
                    break
                words += len(following.split())
            return i + 1, words
    return None, None


def check(repo_root: Path) -> list:
    loader = _load_corpus_loader(repo_root)
    corpus = loader.load_corpus(repo_root)
    components = _get(corpus, "components")
    graph = _get(corpus, "graph")

    bundle = {}
    rows = graph.execute(
        "SELECT component_id, generator_words, criterion_words_max FROM bundle_size"
    ).fetchall()
    for row in rows:
        bundle[row[0]] = (int(row[1]), int(row[2]))

    deps_by_comp = {name: [_slug(d) for d in _deps(comp)] for name, comp in components.items()}

    findings = []
    for name in sorted(components):
        comp = components[name]
        root = _get(comp, "root")
        file = _get(root, "rel_path")
        gen_words, crit_words = bundle.get(name, (0, 0))
        values = {
            "generated_code_loc": _generated_loc(repo_root, name),
            "generator_words": gen_words,
            "criterion_words_max": crit_words,
            "requirement_count": len(_get(comp, "requirements")),
            "interface_surface": _interface_surface(comp),
            "fan_out": len(deps_by_comp[name]),
            "fan_in": sum(1 for other, deps in deps_by_comp.items() if other != name and name in deps),
            "guarantee_count": len(_get(comp, "interface_guarantees")),
            "acceptance_count": len(_get(comp, "acceptance")),
        }

        over_warn = []
        for dim, warn, fail in _THRESHOLDS:
            value = values[dim]
            severity, limit = _severity(value, warn, fail)
            if severity is not None:
                over_warn.append(f"{dim}={value}")
                findings.append(_finding(
                    "R-SIZE-001", severity, file, 1,
                    f"{name}: {dim} is {value}, above the {severity} threshold of {limit} ({_CAPS_DOC})",
                ))

        if len(over_warn) >= 2:
            findings.append(_finding(
                "R-SIZE-002", "warn", file, 1,
                f"{name}: {len(over_warn)} size-cap dimensions over their warn thresholds at once "
                f"({', '.join(over_warn)}); see {_CAPS_DOC}'s decomposition-signal rule",
            ))

        line, words = _purpose(root)
        if line is not None:
            severity, limit = _severity(words, _PURPOSE_WARN, _PURPOSE_FAIL)
            if severity is not None:
                findings.append(_finding(
                    "R-SIZE-004", severity, file, line,
                    f"{name}: Purpose section has {words} words, above the {severity} threshold of {limit} ({_CAPS_DOC})",
                ))

    for doc in _get(corpus, "docs"):
        if _get(doc, "doc_type") in ("component-requirement", "component-acceptance"):
            words = len(_get(doc, "body").split())
            severity, limit = _severity(words, _FILE_WARN, _FILE_FAIL)
            if severity is not None:
                rel = _get(doc, "rel_path")
                findings.append(_finding(
                    "R-SIZE-003", severity, rel, 1,
                    f"{rel} has {words} words, above the per-file {severity} threshold of {limit}",
                ))

    findings.sort(key=lambda f: f["file"])
    return findings
