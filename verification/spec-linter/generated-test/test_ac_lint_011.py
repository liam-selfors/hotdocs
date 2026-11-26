# hotdocs-criterion: sha256:dd8993ce95247193a458ee51ecb9e2a376e73bdb5420768a19703a526604e889
import json
from pathlib import Path

import spec_linter


GLOSSARY_DEF = (
    "a bounded, process-local store of rendered widget fragments keyed by "
    "their spec bundle hash, consulted before any rendering step runs and "
    "invalidated whenever the owning component's interface directory changes "
    "on disk."
)

# Near-verbatim: one word changed ("consulted" -> "checked"), overlap well above 0.8.
LOCAL_DEF = (
    "a bounded, process-local store of rendered widget fragments keyed by "
    "their spec bundle hash, checked before any rendering step runs and "
    "invalidated whenever the owning component's interface directory changes "
    "on disk."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **Widget cache** — " + GLOSSARY_DEF + "\n"
        "- **Gate** — one verification step in the pipeline.\n",
    )
    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
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
        "## Purpose\n"
        "\n"
        "Foo renders widgets for its callers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: rendering widgets.\n"
        "- Out of scope: storing widgets permanently.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **Widget cache** — " + LOCAL_DEF + "\n"
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
        "- Initial draft.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST render a widget when asked.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget request\n"
        "When foo renders it\n"
        "Then a widget is returned\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Rendering completes within 1 second, measured by a timer.\n",
    )


def lint011_fails(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-LINT-011" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_near_verbatim_glossary_copy_fails_r_lint_011(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    hits = lint011_fails(findings)
    assert hits, "expected a fail-severity R-LINT-011 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings]
    )
    assert any("components/foo" in str(field(f, "file")) for f in hits)
    assert field(report, "hard_failures") >= 1


def test_cli_json_reports_r_lint_011_fail(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-011" and f["severity"] == "fail"
    ]
    assert hits
    assert doc["summary"]["hard_failures"] >= 1