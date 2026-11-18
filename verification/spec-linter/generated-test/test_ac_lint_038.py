# hotdocs-criterion: sha256:2d2557209a09d836abbc2fc64b1f9b818d8e65c4b8963880e1c6a0905a5f0b1b
"""AC-LINT-038: the depends_on graph's cycle check (R-LINT-004) over
architecture docs reports exactly the docs on the cycle, and nothing
when there is no cycle."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _arch_doc(doc_id, depends_on):
    lines = [
        "---",
        "id: " + doc_id,
        "title: Architecture " + doc_id,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: [" + ", ".join(depends_on) + "]",
        "---",
        "",
        "# Architecture " + doc_id,
        "",
        "## Purpose",
        "",
        "A synthetic architecture document used as a lint fixture.",
        "",
        "## Change log",
        "",
        "- Initial draft.",
        "",
    ]
    return "\n".join(lines)


def _build_corpus(repo_root: Path, graph: dict) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    for doc_id, deps in graph.items():
        _write(specs / "architecture" / (doc_id + ".md"), _arch_doc(doc_id, deps))


def _normalized_file(finding) -> str:
    return str(field(finding, "file")).replace("\\", "/")


def _r004_findings(report):
    return [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-004"
    ]


def test_cycle_between_arch_a_and_arch_b_reported_once_without_arch_c(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(
        repo_root,
        {
            "arch-a": ["arch-b"],
            "arch-b": ["arch-a"],
            "arch-c": ["arch-a"],
        },
    )

    report = spec_linter.lint(None, repo_root)

    arch_fail = [
        f
        for f in _r004_findings(report)
        if field(f, "severity") == "fail"
        and "specs/architecture/" in _normalized_file(f)
    ]
    assert len(arch_fail) == 1, [
        (field(f, "file"), field(f, "message")) for f in _r004_findings(report)
    ]

    message = str(field(arch_fail[0], "message"))
    assert "arch-a" in message, message
    assert "arch-b" in message, message
    assert "arch-c" not in message, message


def test_no_cycle_yields_no_r_lint_004_finding(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(
        repo_root,
        {
            "arch-a": [],
            "arch-c": ["arch-a"],
        },
    )

    report = spec_linter.lint(None, repo_root)

    found = _r004_findings(report)
    assert found == [], [(field(f, "file"), field(f, "message")) for f in found]