"""Citation checker: verifies that every citation in a spec corpus resolves."""

import importlib.util
import re
import sys
from pathlib import Path

_DEP_SLUG = "corpus-loader"
_DEP_MODULE = "corpus_loader"

_D_CITE_RE = re.compile(r"(?<![A-Za-z0-9_\-])D(\d+)(?![A-Za-z0-9_])")
_POINTER_RE = re.compile(r"`([^`]+)`'s\s+\"([^\"]+)\"\s+section")
_GLOSSARY_CITE_RE = re.compile(r"the\s+glossary's\s+\"([^\"]*)\"")
_GLOSSARY_HEADER_RE = re.compile(r"^- \*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^#+\s+(.*)$")
_D_ID_RE = re.compile(r"^D(\d+)$")


def _get(obj, name):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_dependency(repo_root):
    dep_dir = repo_root / "gen" / _DEP_SLUG
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / _DEP_SLUG
    flat = dep_dir / f"{_DEP_MODULE}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(_DEP_MODULE, flat)
    else:
        pkg = dep_dir / _DEP_MODULE
        spec = importlib.util.spec_from_file_location(
            _DEP_MODULE, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DEP_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _exempt(value):
    m = _D_ID_RE.match(value)
    return bool(m) and 1 <= int(m.group(1)) <= 14


def _finding(rule_id, file, line, message):
    return {
        "rule_id": rule_id,
        "severity": "fail",
        "file": file,
        "line": line,
        "message": message,
    }


def _field_line(text, field):
    for i, line in enumerate(text.splitlines()):
        if line.startswith(field + ":"):
            return i + 1
    return 1


def _as_list(value):
    if isinstance(value, list):
        return value
    return [value]


def _headings(text):
    found = set()
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            found.add(m.group(1).strip())
    return found


def _glossary_headers(repo_root):
    path = repo_root / "specs" / "glossary.md"
    headers = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _GLOSSARY_HEADER_RE.match(line)
            if m:
                headers.add(" ".join(m.group(1).split()))
    return headers


def _decision_exists(repo_root, value):
    return (repo_root / "specs" / "decisions" / f"{value}.md").is_file()


def _check_live(repo_root, rel, text, body, glossary, findings):
    offset = max(0, len(text.splitlines()) - len(body.split("\n")))

    def line_at(pos):
        return offset + body.count("\n", 0, pos) + 1

    for m in _D_CITE_RE.finditer(body):
        value = f"D{m.group(1)}"
        if _exempt(value) or _decision_exists(repo_root, value):
            continue
        findings.append(_finding(
            "R-CITE-001", rel, line_at(m.start()),
            f"citation {value} does not resolve to specs/decisions/{value}.md",
        ))

    for m in _POINTER_RE.finditer(body):
        target = re.sub(r"\s+", "", m.group(1))
        if target.startswith("<"):
            continue
        section = m.group(2)
        path = repo_root / target
        if not path.is_file():
            findings.append(_finding(
                "R-CITE-002", rel, line_at(m.start()),
                f"pointer to {target}: file does not exist",
            ))
        elif section not in _headings(path.read_text(encoding="utf-8")):
            findings.append(_finding(
                "R-CITE-002", rel, line_at(m.start()),
                f"pointer to {target}: no heading \"{section}\"",
            ))

    for m in _GLOSSARY_CITE_RE.finditer(body):
        term = " ".join(m.group(1).split())
        if term[-1:] in (",", ".", ";", ":"):
            term = term[:-1]
        if not term[:1].isalnum():
            continue
        if term not in glossary:
            findings.append(_finding(
                "R-CITE-003", rel, line_at(m.start()),
                f"glossary citation \"{term}\" does not resolve to a glossary entry",
            ))


def _check_decision(repo_root, rel, text, fm, decisions_by_rel, findings):
    if "supersedes" in fm:
        line = _field_line(text, "supersedes")
        for value in _as_list(fm["supersedes"]):
            value = str(value)
            if not _D_ID_RE.match(value) or _exempt(value):
                continue
            target_rel = f"specs/decisions/{value}.md"
            if not _decision_exists(repo_root, value):
                findings.append(_finding(
                    "R-CITE-004", rel, line,
                    f"supersedes {value} does not resolve to {target_rel}",
                ))
                continue
            target = decisions_by_rel.get(target_rel)
            status = _get(target, "frontmatter").get("status") if target is not None else None
            if status != "deprecated":
                findings.append(_finding(
                    "R-CITE-004", rel, line,
                    f"supersedes {value}, but {target_rel} is not status: deprecated",
                ))

    if "builds_on" in fm:
        line = _field_line(text, "builds_on")
        for value in _as_list(fm["builds_on"]):
            value = str(value)
            if _exempt(value) or _decision_exists(repo_root, value):
                continue
            findings.append(_finding(
                "R-CITE-005", rel, line,
                f"builds_on {value} does not resolve to specs/decisions/{value}.md",
            ))


def check(repo_root):
    repo_root = Path(repo_root)
    loader = _load_dependency(repo_root)
    corpus = loader.load_corpus(repo_root)
    docs = list(_get(corpus, "docs"))
    glossary = _glossary_headers(repo_root)

    decisions = [d for d in docs if _get(d, "doc_type") == "decision"]
    decisions_by_rel = {_get(d, "rel_path"): d for d in decisions}

    superseded_by = {}
    for d in decisions:
        fm = _get(d, "frontmatter")
        if "supersedes" in fm:
            for value in _as_list(fm["supersedes"]):
                superseded_by.setdefault(str(value), set()).add(_get(d, "rel_path"))

    findings = []
    for doc in docs:
        rel = _get(doc, "rel_path")
        text = Path(_get(doc, "path")).read_text(encoding="utf-8")
        body = _get(doc, "body")
        fm = _get(doc, "frontmatter")
        if _get(doc, "doc_type") != "decision":
            _check_live(repo_root, rel, text, body, glossary, findings)
            continue
        _check_decision(repo_root, rel, text, fm, decisions_by_rel, findings)
        if fm.get("status") == "deprecated":
            stem = Path(rel).stem
            others = superseded_by.get(stem, set()) - {rel}
            if not others:
                findings.append(_finding(
                    "R-CITE-004", rel, _field_line(text, "status"),
                    f"{stem} is status: deprecated but no other decision supersedes it",
                ))

    findings.sort(key=lambda f: f["file"])
    return findings
