# hotdocs-criterion: sha256:699616dba3c9dc35cc20af6d79c1e3d0692daacb42fc0eda76d32a4b64309e2a
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def arch_doc(doc_id, depends_on):
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        + "id: " + doc_id + "\n"
        + "title: " + doc_id.replace("-", " ").title() + "\n"
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


def build_repo(root, docs):
    write(root / "specs" / "glossary.md", "# Glossary\n\n- **Fixture term** — a term used only by this test.\n")
    for doc_id, deps in docs.items():
        write(root / "specs" / "architecture" / (doc_id + ".md"), arch_doc(doc_id, deps))


def rule_findings(report, rule_id):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == rule_id]


def is_architecture_file(finding):
    file_value = str(field(finding, "file")).replace("\\", "/")
    return "specs/architecture/" in file_value


def test_cycle_among_architecture_docs_reported_once_naming_only_cycle_members(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(
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
        for f in rule_findings(report, "R-LINT-004")
        if field(f, "severity") == "fail" and is_architecture_file(f)
    ]
    assert len(cycle_findings) == 1, [
        (field(f, "file"), field(f, "message")) for f in cycle_findings
    ]
    message = str(field(cycle_findings[0], "message"))
    assert "arch-a" in message
    assert "arch-b" in message
    assert "arch-c" not in message


def test_acyclic_architecture_docs_have_no_cycle_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(
        repo_root,
        {
            "arch-a": [],
            "arch-c": ["arch-a"],
        },
    )

    report = spec_linter.lint(None, repo_root)

    cycle_findings = rule_findings(report, "R-LINT-004")
    assert cycle_findings == [], [
        (field(f, "file"), field(f, "message")) for f in cycle_findings
    ]