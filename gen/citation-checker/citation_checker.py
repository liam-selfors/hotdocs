"""Citation checker: reports every citation in a spec corpus that does not resolve.

Covers decision-number citations (R-CITE-001), section pointers into other
files (R-CITE-002), glossary citations (R-CITE-003), and the `supersedes`
(R-CITE-004) and `builds_on` (R-CITE-005) links between decision records.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path

_DEP_SLUG = "corpus-loader"
_DEP_MODULE = "corpus_loader"

_SEVERITY = "fail"
_FROZEN_MAX = 14

_DECISION_CITE = re.compile(r"\bD(\d+)\b")
_POINTER = re.compile(r"`([^`]+)`'s\s+\"([^\"]+)\"\s+section")
_GLOSSARY_CITE = re.compile(r"the\s+glossary's\s+\"([^\"]*)\"")
_HEADING = re.compile(r"^#+\s+(.+?)\s*$")
_GLOSSARY_ENTRY = re.compile(r"^- \*\*(.+?)\*\*")
_DECISION_ID = re.compile(r"D(\d+)")


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(parent.parent for parent in here.parents if parent.name == "gen")


def _load_dependency(repo_root: Path, slug: str, module_name: str):
    base = repo_root / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    digest = hashlib.sha1(str(base.resolve()).encode("utf-8")).hexdigest()[:16]
    load_name = f"_citation_checker_dep_{module_name}_{digest}"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(load_name, flat)
    else:
        package_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            load_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _finding(rule_id: str, rel_path: str, line: int, message: str) -> dict:
    return {
        "rule_id": rule_id,
        "severity": _SEVERITY,
        "file": rel_path,
        "line": line,
        "message": message,
    }


def _values(value) -> list:
    items = value if isinstance(value, list) else [value]
    return [str(item) for item in items if str(item) != ""]


def _key_line(lines: list, offset: int, key: str) -> int:
    pattern = re.compile(rf"{re.escape(key)}\s*:")
    return next(
        (index + 1 for index, line in enumerate(lines[:offset]) if pattern.match(line)),
        1,
    )


def _glossary_headers(repo_root: Path) -> set:
    path = repo_root / "specs" / "glossary.md"
    if not path.is_file():
        return set()
    headers = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _GLOSSARY_ENTRY.match(line)
        if match:
            headers.add(match.group(1))
    return headers


def _headings(path: Path) -> set:
    headings = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _HEADING.match(line)
        if match:
            headings.add(match.group(1))
    return headings


def _live_findings(repo_root: Path, rel: str, body: str, offset: int, glossary: set) -> list:
    def line_of(pos: int) -> int:
        return offset + body.count("\n", 0, pos) + 1

    findings = []

    for match in _DECISION_CITE.finditer(body):
        number = int(match.group(1))
        if 1 <= number <= _FROZEN_MAX:
            continue
        name = f"D{match.group(1)}"
        if not (repo_root / "specs" / "decisions" / f"{name}.md").is_file():
            findings.append(_finding(
                "R-CITE-001", rel, line_of(match.start()),
                f"{name} does not resolve to specs/decisions/{name}.md",
            ))

    for match in _POINTER.finditer(body):
        target = re.sub(r"\s+", "", match.group(1))
        if target.startswith("<"):
            continue
        section = match.group(2)
        target_path = repo_root / target
        if not target_path.is_file():
            findings.append(_finding(
                "R-CITE-002", rel, line_of(match.start()),
                f"`{target}` does not exist",
            ))
        elif section not in _headings(target_path):
            findings.append(_finding(
                "R-CITE-002", rel, line_of(match.start()),
                f"`{target}` has no heading \"{section}\"",
            ))

    for match in _GLOSSARY_CITE.finditer(body):
        term = match.group(1)
        if term[-1:] in (",", ".", ";", ":") and term:
            term = term[:-1]
        if not term[:1].isalnum():
            continue
        term = " ".join(term.split())
        if term not in glossary:
            findings.append(_finding(
                "R-CITE-003", rel, line_of(match.start()),
                f"glossary term \"{term}\" has no entry in specs/glossary.md",
            ))

    return findings


def _link_findings(repo_root: Path, doc, rel: str, lines: list, offset: int,
                   by_rel: dict, decisions: list) -> list:
    findings = []
    frontmatter = _get(doc, "frontmatter") or {}

    for value in _values(_get(frontmatter, "supersedes", [])):
        if not _DECISION_ID.fullmatch(value):
            continue
        target_rel = f"specs/decisions/{value}.md"
        line = _key_line(lines, offset, "supersedes")
        if not (repo_root / target_rel).is_file():
            findings.append(_finding(
                "R-CITE-004", rel, line,
                f"supersedes {value} does not resolve to {target_rel}",
            ))
        elif _get(_get(by_rel.get(target_rel), "frontmatter") or {}, "status") != "deprecated":
            findings.append(_finding(
                "R-CITE-004", rel, line,
                f"supersedes {value} but {target_rel} is not status: deprecated",
            ))

    if _get(doc, "doc_type") == "decision" and _get(frontmatter, "status") == "deprecated":
        stem = Path(rel).stem
        named = any(
            stem in _values(_get(_get(other, "frontmatter") or {}, "supersedes", []))
            for other in decisions
            if other is not doc
        )
        if not named:
            findings.append(_finding(
                "R-CITE-004", rel, _key_line(lines, offset, "status"),
                f"{stem} is status: deprecated but no other decision supersedes it",
            ))

    for value in _values(_get(frontmatter, "builds_on", [])):
        match = _DECISION_ID.fullmatch(value)
        if match and 1 <= int(match.group(1)) <= _FROZEN_MAX:
            continue
        if not (match and (repo_root / "specs" / "decisions" / f"{value}.md").is_file()):
            findings.append(_finding(
                "R-CITE-005", rel, _key_line(lines, offset, "builds_on"),
                f"builds_on {value} does not resolve to specs/decisions/{value}.md",
            ))

    return findings


def check(repo_root: Path) -> list[dict]:
    """Return every unresolved citation in the corpus under `repo_root`."""
    repo_root = Path(repo_root)
    loader = _load_dependency(repo_root, _DEP_SLUG, _DEP_MODULE)
    corpus = loader.load_corpus(repo_root)
    docs = list(_get(corpus, "docs"))
    by_rel = {_get(doc, "rel_path"): doc for doc in docs}
    decisions = [doc for doc in docs if _get(doc, "doc_type") == "decision"]
    glossary = _glossary_headers(repo_root)

    findings = []
    for doc in docs:
        rel = _get(doc, "rel_path")
        body = _get(doc, "body")
        text = Path(_get(doc, "path")).read_text(encoding="utf-8")
        lines = text.splitlines()
        offset = 0 if body == text else len(lines) - len(body.split("\n"))

        doc_findings = []
        if _get(doc, "doc_type") != "decision":
            doc_findings.extend(_live_findings(repo_root, rel, body, offset, glossary))
        doc_findings.extend(
            _link_findings(repo_root, doc, rel, lines, offset, by_rel, decisions)
        )
        doc_findings.sort(key=lambda finding: finding["line"])
        findings.extend(doc_findings)
    return findings