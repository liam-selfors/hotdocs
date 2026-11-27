# hotdocs-criterion: sha256:c7a4f556993900422e976c7e481be9a5b0a79c95ca6f3fa5f4a4e5914c9bfd65
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_component(repo_root, requirement_bodies):
    comp = repo_root / "specs" / "components" / "widgets"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widgets\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widgets/\n"
        "---\n"
        "\n"
        "# Widgets\n"
        "\n"
        "A fixture component.\n",
    )
    for req_id, body in requirement_bodies:
        write(
            comp / "requirements" / (req_id + ".md"),
            "# " + req_id + "\n"
            "\n"
            "**" + req_id + "** \u2014 " + body + "\n",
        )
        ac_id = "AC-" + req_id[len("R-"):]
        write(
            comp / "acceptance" / (ac_id + ".md"),
            "# " + ac_id + "\n"
            "\n"
            "Covers: " + req_id + "\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given a widget\n"
            "When it is used\n"
            "Then it works\n"
            "```\n",
        )
    return comp


def cite_findings(repo_root):
    findings = citation_checker.check(repo_root)
    return [f for f in findings if field(f, "rule_id") == "R-CITE-003"]


def req_rel(req_id):
    return "specs/components/widgets/requirements/" + req_id + ".md"


def test_only_missing_glossary_entry_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Widget** \u2014 a small fixture thing.\n",
    )
    build_component(
        repo_root,
        [
            ("R-WID-001", "The tool MUST handle the glossary's \"Widget\" as defined."),
            ("R-WID-002", "The tool MUST handle the glossary's \"Gizmo\" as defined."),
        ],
    )

    found = cite_findings(repo_root)

    files = [field(f, "file") for f in found]
    assert len(found) == 1, found
    assert files == [req_rel("R-WID-002")], found
    assert isinstance(field(found[0], "line"), int)


def test_wrap_comma_and_placeholder_resolve_only_case_mismatch_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Widget** \u2014 a small fixture thing.\n"
        "- **Blue Widget** \u2014 a widget that is blue.\n",
    )
    build_component(
        repo_root,
        [
            (
                "R-WID-001",
                "The tool MUST handle the glossary's \"Blue\n  Widget\" as defined.",
            ),
            (
                "R-WID-002",
                "The tool MUST handle the glossary's \"Widget,\" as defined.",
            ),
            (
                "R-WID-003",
                "The tool MUST handle the glossary's \"widget\" as defined.",
            ),
            (
                "R-WID-004",
                "A citation takes the form the glossary's \"<Term>\" in prose.",
            ),
        ],
    )

    found = cite_findings(repo_root)

    files = [field(f, "file") for f in found]
    assert len(found) == 1, found
    assert files == [req_rel("R-WID-003")], found
    assert isinstance(field(found[0], "line"), int)