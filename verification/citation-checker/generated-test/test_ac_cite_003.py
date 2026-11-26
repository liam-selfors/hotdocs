# hotdocs-criterion: sha256:09bb00eb5fc3c56a63657565cfbe19b2b2a317814fd9315d4fdf1f9adbde3404
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this fixture corpus.\n"
    "\n"
    "- **Widget** — a small fixture thing used in tests.\n"
    "- **Spec bundle** — the full set of files one step needs for a\n"
    "  component.\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "A fixture component.\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, requirement_bodies):
    specs = repo_root / "specs"
    write(specs / "glossary.md", GLOSSARY)
    comp = specs / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nrun() -> None\n```\n\nDoes nothing.\n",
    )
    for num, body in requirement_bodies.items():
        rid = "R-FOO-" + num
        aid = "AC-FOO-" + num
        write(comp / "requirements" / (rid + ".md"), "# " + rid + "\n\n" + body)
        write(
            comp / "acceptance" / (aid + ".md"),
            "# " + aid + "\n\nCovers: " + rid + "\nKind: judged\n\n"
            "Given a fixture\nWhen it runs\nThen it works\n",
        )


def cite_findings(repo_root):
    findings = citation_checker.check(repo_root)
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-CITE-003":
            out.append(str(field(f, "file")).replace("\\", "/"))
    return out


REQ_DIR = "specs/components/foo/requirements/"


def test_missing_entry_gets_finding_existing_does_not(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(
        repo_root,
        {
            "001": "**R-FOO-001** — The tool MUST emit each\n"
            "  the glossary's \"Widget\" exactly once.\n",
            "002": "**R-FOO-002** — The tool MUST emit each\n"
            "  the glossary's \"Gizmo\" exactly once.\n",
        },
    )
    files = cite_findings(repo_root)
    assert files == [REQ_DIR + "R-FOO-002.md"], files


def test_wrap_trailing_punct_placeholder_ok_case_mismatch_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(
        repo_root,
        {
            "001": "**R-FOO-001** — The tool MUST read the glossary's \"Spec\n"
            "  bundle\" before it starts.\n",
            "002": "**R-FOO-002** — The tool MUST accept the glossary's \"Widget,\"\n"
            "  and nothing else.\n",
            "003": "**R-FOO-003** — The tool MUST accept the glossary's \"widget\"\n"
            "  and nothing else.\n",
            "004": "**R-FOO-004** — Every the glossary's \"<Term>\" citation\n"
            "  MUST resolve.\n",
        },
    )
    files = cite_findings(repo_root)
    assert files == [REQ_DIR + "R-FOO-003.md"], files