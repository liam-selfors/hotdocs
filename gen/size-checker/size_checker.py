"""Size checker: measures each component of a spec corpus against the size
caps of specs/architecture/size-caps.md (R-SIZE-001 .. R-SIZE-004)."""

import importlib.util
import re
import sys
from pathlib import Path

CAPS_DOC = "specs/architecture/size-caps.md"

# (dimension, warn above, fail above or None for warn-only), in R-SIZE-001's order.
CAPS = [
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

FILE_WARN, FILE_FAIL = 250, 500
PURPOSE_WARN, PURPOSE_FAIL = 80, 150

_LIBRARY_SIG = re.compile(r"^\w+\(.*\)\s*(->|:)")
_PURPOSE_HEADING = re.compile(r"^##\s+Purpose\s*$")
_LEVEL2_HEADING = re.compile(r"^##\s")


def _get(obj, name):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_corpus_loader(repo_root):
    base = Path(repo_root) / "gen" / "corpus-loader"
    if not base.is_dir():
        base = _tool_root() / "gen" / "corpus-loader"
    pkg_init = base / "corpus_loader" / "__init__.py"
    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            "corpus_loader", pkg_init,
            submodule_search_locations=[str(pkg_init.parent)],
        )
    else:
        spec = importlib.util.spec_from_file_location(
            "corpus_loader", base / "corpus_loader.py"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["corpus_loader"] = module
    spec.loader.exec_module(module)
    return module


def _slug(dep):
    dep = str(dep).strip()
    return dep[len("comp-"):] if dep.startswith("comp-") else dep


def _depends_on(root):
    deps = _get(root, "frontmatter").get("depends_on") or []
    if isinstance(deps, str):
        deps = [deps]
    return [_slug(d) for d in deps if str(d).strip()]


def _generated_code_loc(repo_root, name):
    gen_dir = Path(repo_root) / "gen" / name
    total = 0
    if gen_dir.is_dir():
        for py in sorted(gen_dir.rglob("*.py")):
            if not py.is_file():
                continue
            for line in py.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    total += 1
    return total


def _first_fence(body):
    collected = None
    for line in body.splitlines():
        if line.strip().startswith("```"):
            if collected is None:
                collected = []
                continue
            return collected
        if collected is not None:
            collected.append(line)
    return collected or []


def _joined(lines):
    out = []
    buf = ""
    for line in lines:
        if line.endswith("\\"):
            buf += line[:-1]
            continue
        out.append(buf + line)
        buf = ""
    if buf:
        out.append(buf)
    return out


def _interface_surface(comp):
    count = 0
    cli = _get(comp, "interface_cli")
    if cli is not None:
        for line in _joined(_first_fence(_get(cli, "body"))):
            if line.strip():
                count += 1
    lib = _get(comp, "interface_library")
    if lib is not None:
        for line in _joined(_first_fence(_get(lib, "body"))):
            if _LIBRARY_SIG.match(line):
                count += 1
    count += len(_get(comp, "interface_data"))
    return count


def _severity(value, warn, fail):
    if fail is not None and value > fail:
        return "fail", fail
    if value > warn:
        return "warn", warn
    return None, None


def _purpose(root):
    lines = Path(_get(root, "path")).read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines):
        if _PURPOSE_HEADING.match(line):
            words = 0
            for nxt in lines[idx + 1:]:
                if _LEVEL2_HEADING.match(nxt):
                    break
                words += len(nxt.split())
            return idx + 1, words
    return None, None


def _finding(rule_id, severity, file, line, message):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "file": file,
        "line": line,
        "message": message,
    }


def check(repo_root):
    repo_root = Path(repo_root)
    loader = _load_corpus_loader(repo_root)
    corpus = loader.load_corpus(repo_root)

    docs = _get(corpus, "docs")
    order = {_get(doc, "rel_path"): i for i, doc in enumerate(docs)}
    components = _get(corpus, "components")
    rooted = {
        name: comp for name, comp in components.items()
        if _get(comp, "root") is not None
    }

    graph = _get(corpus, "graph")
    bundle = {
        str(row[0]): (row[1], row[2])
        for row in graph.execute(
            "SELECT component_id, generator_words, criterion_words_max FROM bundle_size"
        ).fetchall()
    }

    deps = {name: _depends_on(_get(comp, "root")) for name, comp in rooted.items()}

    findings = []
    for name in sorted(rooted):
        comp = rooted[name]
        root = _get(comp, "root")
        root_file = _get(root, "rel_path")
        gen_words, crit_words = bundle.get(name, (0, 0))
        values = {
            "generated_code_loc": _generated_code_loc(repo_root, name),
            "generator_words": int(gen_words or 0),
            "criterion_words_max": int(crit_words or 0),
            "requirement_count": len(_get(comp, "requirements")),
            "interface_surface": _interface_surface(comp),
            "fan_out": len(deps[name]),
            "fan_in": sum(1 for other, d in deps.items() if other != name and name in d),
            "guarantee_count": len(_get(comp, "interface_guarantees")),
            "acceptance_count": len(_get(comp, "acceptance")),
        }

        over_warn = []
        for dim, warn, fail in CAPS:
            value = values[dim]
            sev, limit = _severity(value, warn, fail)
            if sev is None:
                continue
            over_warn.append((dim, value))
            findings.append(_finding(
                "R-SIZE-001", sev, root_file, 1,
                f"{name}: {dim} is {value}, above the {sev} threshold of {limit} ({CAPS_DOC})",
            ))

        if len(over_warn) >= 2:
            listed = ", ".join(f"{dim}={value}" for dim, value in over_warn)
            findings.append(_finding(
                "R-SIZE-002", "warn", root_file, 1,
                f"{name}: {len(over_warn)} size-cap dimensions over their warn thresholds "
                f"at once ({listed}); see {CAPS_DOC}'s decomposition-signal rule",
            ))

        unit_docs = list(_get(comp, "requirements").values()) + list(_get(comp, "acceptance").values())
        for doc in unit_docs:
            words = len(_get(doc, "body").split())
            sev, limit = _severity(words, FILE_WARN, FILE_FAIL)
            if sev is None:
                continue
            rel = _get(doc, "rel_path")
            findings.append(_finding(
                "R-SIZE-003", sev, rel, 1,
                f"{rel} has {words} words, above the per-file {sev} threshold of {limit}",
            ))

        line, words = _purpose(root)
        if line is not None:
            sev, limit = _severity(words, PURPOSE_WARN, PURPOSE_FAIL)
            if sev is not None:
                findings.append(_finding(
                    "R-SIZE-004", sev, root_file, line,
                    f"{name}: Purpose section has {words} words, above the {sev} "
                    f"threshold of {limit} ({CAPS_DOC})",
                ))

    findings.sort(key=lambda f: order[f["file"]])
    return findings
