# hotdocs-criterion: sha256:4afabea7a812311e37279498436751cdb210eeb730895762b596db2ba7b7414e
from pathlib import Path

import citation_checker


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for the fixture corpus.\n"
    "\n"
    "- **Widget** — a small fixture thing used by tests.\n"
    "- **Big Widget** — a larger fixture thing, spanning\n"
    "  more than one line of definition text.\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root, requirement_bodies):
    """Build a fixture corpus with one sealed draft component `foo`.

    requirement_bodies maps a requirement id (e.g. "R-FOO-001") to its
    full file text. Each gets a matching acceptance file.
    """
    specs = repo_root / "specs"
    write(specs / "glossary.md", GLOSSARY)
    comp = specs / "components" / "foo"
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component for citation checking.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: fixtures.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See requirements.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See interface.\n"
        "\n"
        "## Data\n"
        "\n"
        "None.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See acceptance.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "None.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Created.\n"
    )
    write(comp / "component.md", component_md)
    for req_id, body in requirement_bodies.items():
        write(comp / "requirements" / (req_id + ".md"), body)
        ac_id = "AC-" + req_id[len("R-"):]
        ac_text = (
            "# " + ac_id + "\n"
            "\n"
            "Covers: " + req_id + "\n"
            "Kind: generated-test\n"
            "\n"
            "Given a fixture\n"
            "When it runs\n"
            "Then it works\n"
        )
        write(comp / "acceptance" / (ac_id + ".md"), ac_text)


def cite_findings(repo_root):
    findings = citation_checker.check(repo_root)
    return [f for f in findings if field(f, "rule_id") == "R-CITE-003"]


def req_path(req_id):
    return "specs/components/foo/requirements/" + req_id + ".md"


def test_missing_glossary_entry_gets_finding_existing_does_not(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(
        repo_root,
        {
            "R-FOO-001": (
                "**R-FOO-001** — The tool MUST handle each item as\n"
                "described in the glossary's \"Widget\" entry.\n"
            ),
            "R-FOO-002": (
                "**R-FOO-002** — The tool MUST handle each item as\n"
                "described in the glossary's \"Gizmo\" entry.\n"
            ),
        },
    )
    findings = cite_findings(repo_root)
    files = [field(f, "file") for f in findings]
    assert len(findings) == 1, findings
    assert files == [req_path("R-FOO-002")]
    f = findings[0]
    assert field(f, "severity") in ("fail", "warn")
    assert isinstance(field(f, "line"), int)
    assert isinstance(field(f, "message"), str)


def test_wrap_trailing_punctuation_placeholder_ok_case_mismatch_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(
        repo_root,
        {
            # Wrapped across two lines: whitespace collapses to "Big Widget".
            "R-FOO-001": (
                "**R-FOO-001** — The tool MUST treat it per the glossary's \"Big\n"
                "  Widget\" entry when sizing.\n"
            ),
            # Trailing comma inside the closing quote is not part of the term.
            "R-FOO-002": (
                "**R-FOO-002** — The tool MUST, per the glossary's \"Widget,\"\n"
                "handle each item.\n"
            ),
            # Different letter case: case-exact match fails.
            "R-FOO-003": (
                "**R-FOO-003** — The tool MUST handle each item per the\n"
                "glossary's \"widget\" entry.\n"
            ),
            # Placeholder, not a citation.
            "R-FOO-004": (
                "**R-FOO-004** — A citation is written as the glossary's \"<Term>\"\n"
                "with the entry header quoted.\n"
            ),
        },
    )
    findings = cite_findings(repo_root)
    files = [field(f, "file") for f in findings]
    assert len(findings) == 1, findings
    assert files == [req_path("R-FOO-003")]
    assert field(findings[0], "severity") in ("fail", "warn")