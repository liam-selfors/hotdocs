# hotdocs-criterion: sha256:4afabea7a812311e37279498436751cdb210eeb730895762b596db2ba7b7414e
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this fixture corpus.\n"
    "\n"
    "- **Widget** — a small fixture thing used by tests.\n"
    "- **Criterion test filename** — the deterministic filename of a\n"
    "  criterion's test file.\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: ratified\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "last_ratified_commit: 0000000\n"
    "---\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Does a small fixture job.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the fixture job.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "None.\n"
    "\n"
    "## Behavior\n"
    "\n"
    "See `requirements/`.\n"
    "\n"
    "## Interfaces\n"
    "\n"
    "See `interface/`.\n"
    "\n"
    "## Data\n"
    "\n"
    "See `interface/data/`.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "See `acceptance/`.\n"
    "\n"
    "## Non-functional constraints\n"
    "\n"
    "See `constraints.md`.\n"
    "\n"
    "## Open questions\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial version.\n"
)


def build_fixture(repo_root, requirements):
    specs = repo_root / "specs"
    specs.mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY)
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    for i, body in enumerate(requirements, start=1):
        rid = "R-FOO-%03d" % i
        aid = "AC-FOO-%03d" % i
        (comp / "requirements" / (rid + ".md")).write_text(
            "# " + rid + "\n\n**" + rid + "** — " + body + "\n"
        )
        (comp / "acceptance" / (aid + ".md")).write_text(
            "# " + aid + "\n\nCovers: " + rid + "\nKind: llm-judge\n\n"
            "The requirement holds.\n"
        )


def req_path(n):
    return "specs/components/foo/requirements/R-FOO-%03d.md" % n


def cite_findings(repo_root):
    findings = citation_checker.check(repo_root)
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-CITE-003":
            out.append(str(field(f, "file")).replace("\\", "/"))
    return out


def test_missing_glossary_entry_is_flagged_existing_is_not(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(
        repo_root,
        [
            "The component MUST treat each input as the glossary's \"Widget\" defines it.",
            "The component MUST treat each output as the glossary's \"Gizmo\" defines it.",
        ],
    )
    files = cite_findings(Path(repo_root))
    assert files == [req_path(2)]


def test_wrap_punctuation_case_and_placeholder(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(
        repo_root,
        [
            "The component MUST name each file per the glossary's \"Criterion test\n"
            "  filename\" exactly.",
            "The component MUST treat each input as the glossary's \"Widget,\" never\n"
            "  as anything else.",
            "The component MUST treat each input as the glossary's \"widget\" defines it.",
            "A citation takes the form the glossary's \"<Term>\" in prose.",
        ],
    )
    files = cite_findings(Path(repo_root))
    assert files == [req_path(3)]