# hotdocs-criterion: sha256:2d2557209a09d836abbc2fc64b1f9b818d8e65c4b8963880e1c6a0905a5f0b1b
"""AC-LINT-038 (covers R-LINT-004): depends_on cycle detection among
architecture docs names exactly the components on the cycle."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "- **Widget** — a test-only glossary term.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _arch_doc(doc_id, depends_on):
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        + "id: " + doc_id + "\n"
        + "title: " + doc_id + " title\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: " + deps + "\n"
        + "---\n"
        + "\n"
        + "# " + doc_id + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A test architecture document.\n"
        + "\n"
        + "## Change log\n"
        + "\n"
        + "- Initial draft.\n"
    )


def _build_repo(repo_root, docs):
    specs = repo_root / "specs"
    (specs / "architecture").mkdir(parents=True, exist_ok=True)
    _write(specs / "glossary.md", GLOSSARY_TEXT)
    for doc_id, deps in docs.items():
        _write(specs / "architecture" / (doc_id + ".md"), _arch_doc(doc_id, deps))


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def _r004_findings(report):
    return [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-004"
    ]


def _is_architecture_file(finding):
    rel = _norm(field(finding, "file"))
    return rel.startswith("specs/architecture/") or "/specs/architecture/" in rel


def test_cycle_between_arch_a_and_arch_b_reported_once_without_arch_c(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(
        repo_root,
        {
            "arch-a": ["arch-b"],
            "arch-b": ["arch-a"],
            "arch-c": ["arch-a"],
        },
    )

    report = spec_linter.lint(None, repo_root)

    fails = [
        f
        for f in _r004_findings(report)
        if field(f, "severity") == "fail" and _is_architecture_file(f)
    ]
    assert len(fails) == 1, [
        (field(f, "file"), field(f, "message")) for f in _r004_findings(report)
    ]
    message = field(fails[0], "message")
    assert "arch-a" in message
    assert "arch-b" in message
    assert "arch-c" not in message


def test_acyclic_architecture_dependencies_report_no_cycle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(
        repo_root,
        {
            "arch-a": [],
            "arch-c": ["arch-a"],
        },
    )

    report = spec_linter.lint(None, repo_root)

    findings = _r004_findings(report)
    assert findings == [], [
        (field(f, "file"), field(f, "message")) for f in findings
    ]