# hotdocs-criterion: sha256:b1006276864728ce0e0e2cc9f3f42c84fdfb6f05b28efd8dd5068990002f5885
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY_TERM = "Blast radius"
GLOSSARY_DEF = (
    "the minimal set of components `impact-analyzer` determines need "
    "regeneration/re-verification for a given spec change."
)
NEW_NUANCE = (
    "Here, counted only across foo widgets; sealed legacy callers stay "
    "excluded entirely, because their behavior is frozen upstream."
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(definitions_body):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes a foo.\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a foo. **Out of scope:** everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        + definitions_body
        + "\n"
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
        "None.\n"
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
        "None.\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def _build_corpus(repo_root, local_definition_text):
    specs = repo_root / "specs"
    _write(
        specs / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo works\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Foo works\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A foo can be made.\n"
        "\n"
        "### CS-FOO-001\n"
        "Covers: P-FOO\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When a foo is made\n"
        "Then it exists\n"
        "```\n",
    )
    definitions = "- **" + GLOSSARY_TERM + "** — " + local_definition_text + "\n"
    _write(specs / "components" / "foo" / "component.md", _component_md(definitions))
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `make_foo()` MUST return the string `\"foo\"`.\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "One module file, `foo.py`.\n"
        "\n"
        "```\n"
        "make_foo() -> str\n"
        "```\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When make_foo() is called\n"
        "Then the result is \"foo\"\n"
        "```\n",
    )
    _write(
        specs / "components" / "foo" / "constraints.md",
        "# Foo — Non-Functional Constraints\n"
        "\n"
        "- **Pure.** No I/O.\n",
    )
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **" + GLOSSARY_TERM + "** — " + GLOSSARY_DEF + "\n",
    )


def _r011(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-011"]


def test_low_overlap_definition_delta_is_not_flagged(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, NEW_NUANCE)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    flagged = _r011(findings)
    assert flagged == [], "unexpected R-LINT-011 findings: " + repr(flagged)

    capsys.readouterr()
    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert [f for f in data["findings"] if f["rule_id"] == "R-LINT-011"] == []
    assert code in (0, 1)
    if not any(f["severity"] == "fail" for f in data["findings"]):
        assert code == 0


def test_control_verbatim_restatement_is_flagged(tmp_path):
    # Sanity control: the same fixture with the glossary text restated
    # verbatim is a redefinition, so the check is demonstrably active.
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, GLOSSARY_DEF)

    report = spec_linter.lint(None, repo_root)
    flagged = _r011(list(field(report, "findings")))
    assert len(flagged) >= 1
    assert all(field(f, "severity") == "fail" for f in flagged)
    assert any(
        field(f, "file") == "specs/components/foo/component.md" for f in flagged
    )