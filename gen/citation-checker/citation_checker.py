"""citation-checker: checks that every citation in a spec corpus resolves.

Covers decision-number citations, section pointers into other files,
glossary citations, and the ``supersedes`` / ``builds_on`` links between
decision records (R-CITE-001 .. R-CITE-005).
"""

import hashlib
import importlib.util
import re
import sys
from pathlib import Path

_D_CITE = re.compile(r"\bD(\d+)\b")
_POINTER = re.compile(r"`([^`]+)`'s\s+\"([^\"]+)\"\s+section")
_GLOSSARY_CITE = re.compile(r"the\s+glossary's\s+\"([^\"]*)\"")
_GLOSSARY_ENTRY = re.compile(r"^- \*\*(.+?)\*\*", re.MULTILINE)
_HEADING = re.compile(r"^#+[ \t]+(.*?)[ \t]*$", re.MULTILINE)
_FROZEN = re.compile(r"D(\d+)")


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_dependency(repo_root, slug, module_name):
    base = repo_root / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    digest = hashlib.sha256(str(base.resolve()).encode("utf-8")).hexdigest()[:16]
    load_name = f"_citation_checker__{module_name}_{digest}"
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(load_name, flat)
    else:
        pkg = base / module_name
        spec = importlib.util.spec_from_file_location(
            load_name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _finding(rule_id, rel, line, message):
    return {
        "rule_id": rule_id,
        "severity": "fail",
        "file": rel,
        "line": line,
        "message": message,
    }


def _line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def _field_line(text, field):
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith(field + ":"):
            return number
    return 1


def _frozen(value):
    m = _FROZEN.fullmatch(value)
    return bool(m) and 1 <= int(m.group(1)) <= 14


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _decision_key(value):
    return f"specs/decisions/{value}.md"


def _glossary_terms(repo_root):
    path = repo_root / "specs" / "glossary.md"
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    return {" ".join(m.group(1).split()) for m in _GLOSSARY_ENTRY.finditer(text)}


def _headings(path):
    text = path.read_text(encoding="utf-8")
    return {m.group(1) for m in _HEADING.finditer(text)}


def _check_live(repo_root, rel, text, decisions, glossary_terms):
    findings = []
    for m in _D_CITE.finditer(text):
        cited = m.group(0)
        if _frozen(cited):
            continue
        if _decision_key(cited) not in decisions:
            findings.append(_finding(
                "R-CITE-001", rel, _line_of(text, m.start()),
                f"{cited} does not resolve to {_decision_key(cited)}",
            ))
    for m in _POINTER.finditer(text):
        target = re.sub(r"\s+", "", m.group(1))
        if target.startswith("<"):
            continue
        section = m.group(2)
        path = repo_root / target
        line = _line_of(text, m.start())
        if not path.is_file():
            findings.append(_finding(
                "R-CITE-002", rel, line,
                f"pointer to {target}'s \"{section}\" section: file {target} does not exist",
            ))
        elif section not in _headings(path):
            findings.append(_finding(
                "R-CITE-002", rel, line,
                f"pointer to {target}'s \"{section}\" section: no heading \"{section}\" in {target}",
            ))
    for m in _GLOSSARY_CITE.finditer(text):
        raw = m.group(1)
        if not raw[:1].isalnum():
            continue
        term = raw[:-1] if raw[-1] in ",.;:" else raw
        term = " ".join(term.split())
        if term not in glossary_terms:
            findings.append(_finding(
                "R-CITE-003", rel, _line_of(text, m.start()),
                f"the glossary's \"{term}\" does not resolve to an entry in specs/glossary.md",
            ))
    return findings


def _check_decision(doc, rel, text, decisions, superseders):
    findings = []
    fm = _get(doc, "frontmatter")
    for value in _as_list(_get(fm, "supersedes")):
        if _frozen(value):
            continue
        target = decisions.get(_decision_key(value))
        line = _field_line(text, "supersedes")
        if target is None:
            findings.append(_finding(
                "R-CITE-004", rel, line,
                f"supersedes {value}, which does not resolve to {_decision_key(value)}",
            ))
        else:
            status = _get(_get(target, "frontmatter"), "status")
            if status != "deprecated":
                findings.append(_finding(
                    "R-CITE-004", rel, line,
                    f"supersedes {value}, whose status is {status!r}, not 'deprecated'",
                ))
    if _get(fm, "status") == "deprecated":
        named_by = [s for s in superseders.get(Path(rel).stem, []) if s != rel]
        if not named_by:
            findings.append(_finding(
                "R-CITE-004", rel, _field_line(text, "status"),
                "status is deprecated but no other decision's supersedes names it",
            ))
    for value in _as_list(_get(fm, "builds_on")):
        if _frozen(value):
            continue
        if _decision_key(value) not in decisions:
            findings.append(_finding(
                "R-CITE-005", rel, _field_line(text, "builds_on"),
                f"builds_on {value}, which does not resolve to {_decision_key(value)}",
            ))
    return findings


def check(repo_root):
    repo_root = Path(repo_root)
    loader = _load_dependency(repo_root, "corpus-loader", "corpus_loader")
    corpus = loader.load_corpus(repo_root)
    docs = _get(corpus, "docs")
    decisions = {
        _get(doc, "rel_path"): doc
        for doc in docs
        if _get(doc, "doc_type") == "decision"
    }
    superseders = {}
    for rel, doc in decisions.items():
        for value in _as_list(_get(_get(doc, "frontmatter"), "supersedes")):
            superseders.setdefault(value, []).append(rel)
    glossary_terms = _glossary_terms(repo_root)

    findings = []
    for doc in docs:
        rel = _get(doc, "rel_path")
        text = Path(_get(doc, "path")).read_text(encoding="utf-8")
        if _get(doc, "doc_type") == "decision":
            findings.extend(_check_decision(doc, rel, text, decisions, superseders))
        else:
            findings.extend(_check_live(repo_root, rel, text, decisions, glossary_terms))
    return findings