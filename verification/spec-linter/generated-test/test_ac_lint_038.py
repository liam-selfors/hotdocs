# hotdocs-criterion: sha256:c05500b6f09d03a5500f493626d91a5820e5afcfe22e0607a594d49c5d4032e0
"""AC-LINT-038 (covers R-LINT-004): the corpus-wide depends_on graph must be
acyclic; a cycle's finding names every node on it and nothing else."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _arch_doc(doc_id, depends_on):
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        + "id: " + doc_id + "\n"
        + "title: " + doc_id.upper() + " doc\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: " + deps + "\n"
        + "---\n"
        + "\n"
        + "# " + doc_id + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A fixture architecture document.\n"
    )


def _build_corpus(repo_root, graph):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    for doc_id, deps in graph.items():
        _write(specs / "architecture" / (doc_id + ".md"), _arch_doc(doc_id, deps))


def _norm_file(value):
    return str(value).replace("\\", "/")


def _r004_findings(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-004"]


def test_cycle_finding_names_cycle_members_only(tmp_path):
    repo_root = tmp_path
    _build_corpus(
        repo_root,
        {
            "arch-a": ["arch-b"],
            "arch-b": ["arch-a"],
            "arch-c": ["arch-a"],
        },
    )

    report = spec_linter.lint(None, repo_root)

    cycle_findings = [
        f
        for f in _r004_findings(report)
        if field(f, "severity") == "fail"
        and "specs/architecture/" in _norm_file(field(f, "file"))
    ]
    assert len(cycle_findings) == 1, [
        (field(f, "file"), field(f, "message")) for f in _r004_findings(report)
    ]
    message = field(cycle_findings[0], "message")
    assert "arch-a" in message
    assert "arch-b" in message
    assert "arch-c" not in message


def test_acyclic_chain_has_no_cycle_finding(tmp_path):
    repo_root = tmp_path
    _build_corpus(
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