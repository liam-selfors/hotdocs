"""Citation checker: every citation in a spec corpus resolves (R-CITE-001..005)."""

import importlib.util
import re
import sys
from pathlib import Path

_D_CITE = re.compile(r"\bD(\d+)\b")
_POINTER = re.compile(r"`([^`]+)`'s\s+\"([^\"]+)\"\s+section")
_GLOSSARY_CITE = re.compile(r"the\s+glossary's\s+\"([^\"]*)\"")
_GLOSSARY_ENTRY = re.compile(r"^- \*\*(.+?)\*\*", re.M)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_corpus_loader(root):
    base = root / "gen" / "corpus-loader"
    if not base.is_dir():
        base = _tool_root() / "gen" / "corpus-loader"
    flat = base / "corpus_loader.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location("corpus_loader", flat)
    else:
        pkg = base / "corpus_loader"
        spec = importlib.util.spec_from_file_location(
            "corpus_loader",
            pkg / "__init__.py",
            submodule_search_locations=[str(pkg)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["corpus_loader"] = module
    spec.loader.exec_module(module)
    return module


def _finding(rule_id, rel_path, line, message):
    return {
        "rule_id": rule_id,
        "severity": "fail",
        "file": rel_path,
        "line": line,
        "message": message,
    }


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _field_line(text, field):
    return next(
        i
        for i, line in enumerate(text.splitlines(), 1)
        if line.startswith(field + ":")
    )


def _exempt(value):
    m = re.fullmatch(r"D(\d+)", value)
    return m is not None and 1 <= int(m.group(1)) <= 14


def _decision_path(value):
    return f"specs/decisions/{value}.md"


def _headings(path):
    return {
        line.lstrip("#").strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }


def _check_live(root, rel, text, decisions, glossary_headers):
    out = []
    for m in _D_CITE.finditer(text):
        cite = "D" + m.group(1)
        if not _exempt(cite) and _decision_path(cite) not in decisions:
            out.append(
                _finding(
                    "R-CITE-001",
                    rel,
                    _line(text, m.start()),
                    f"{cite} does not resolve to {_decision_path(cite)}",
                )
            )
    for m in _POINTER.finditer(text):
        target = re.sub(r"\s+", "", m.group(1))
        if target.startswith("<"):
            continue
        section = m.group(2)
        path = root / target
        line = _line(text, m.start())
        if not path.is_file():
            out.append(
                _finding(
                    "R-CITE-002",
                    rel,
                    line,
                    f'pointer to `{target}`\'s "{section}" section: '
                    f"file {target} does not exist",
                )
            )
        elif section not in _headings(path):
            out.append(
                _finding(
                    "R-CITE-002",
                    rel,
                    line,
                    f'pointer to `{target}`\'s "{section}" section: '
                    f'{target} has no heading "{section}"',
                )
            )
    for m in _GLOSSARY_CITE.finditer(text):
        raw = m.group(1)
        if not raw[:1].isalnum():
            continue
        term = raw[:-1] if raw[-1] in ",.;:" else raw
        term = " ".join(term.split())
        if term not in glossary_headers:
            out.append(
                _finding(
                    "R-CITE-003",
                    rel,
                    _line(text, m.start()),
                    f'the glossary\'s "{term}" does not resolve to an entry '
                    f"in specs/glossary.md",
                )
            )
    return out


def _check_decision(rel, doc, text, decisions, superseders):
    out = []
    fm = _get(doc, "frontmatter")
    sup = _get(fm, "supersedes")
    if sup and not _exempt(sup):
        line = _field_line(text, "supersedes")
        target = decisions.get(_decision_path(sup))
        if target is None:
            out.append(
                _finding(
                    "R-CITE-004",
                    rel,
                    line,
                    f"supersedes: {sup} does not resolve to {_decision_path(sup)}",
                )
            )
        else:
            status = _get(_get(target, "frontmatter"), "status")
            if status != "deprecated":
                out.append(
                    _finding(
                        "R-CITE-004",
                        rel,
                        line,
                        f"supersedes: {sup} but {_decision_path(sup)} has "
                        f"status {status}, not deprecated",
                    )
                )
    if _get(fm, "status") == "deprecated" and not (
        superseders.get(Path(rel).stem, set()) - {rel}
    ):
        out.append(
            _finding(
                "R-CITE-004",
                rel,
                _field_line(text, "status"),
                f"status: deprecated but no other decision supersedes "
                f"{Path(rel).stem}",
            )
        )
    for entry in _get(fm, "builds_on") or []:
        if not _exempt(entry) and _decision_path(entry) not in decisions:
            out.append(
                _finding(
                    "R-CITE-005",
                    rel,
                    _field_line(text, "builds_on"),
                    f"builds_on entry {entry} does not resolve to "
                    f"{_decision_path(entry)}",
                )
            )
    return out


def check(repo_root):
    root = Path(repo_root)
    loader = _load_corpus_loader(root)
    corpus = loader.load_corpus(root)
    docs = _get(corpus, "docs")

    decisions = {}
    for doc in docs:
        if _get(doc, "doc_type") == "decision":
            decisions[_get(doc, "rel_path")] = doc

    superseders = {}
    for rel, doc in decisions.items():
        sup = _get(_get(doc, "frontmatter"), "supersedes")
        superseders.setdefault(sup, set()).add(rel)

    glossary = root / "specs" / "glossary.md"
    glossary_headers = (
        {
            " ".join(h.split())
            for h in _GLOSSARY_ENTRY.findall(glossary.read_text(encoding="utf-8"))
        }
        if glossary.is_file()
        else set()
    )

    findings = []
    for doc in docs:
        rel = _get(doc, "rel_path")
        text = Path(_get(doc, "path")).read_text(encoding="utf-8")
        if rel in decisions:
            findings.extend(
                _check_decision(rel, doc, text, decisions, superseders)
            )
        else:
            findings.extend(
                _check_live(root, rel, text, decisions, glossary_headers)
            )
    return findings
