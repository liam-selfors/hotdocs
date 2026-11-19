# hotdocs-criterion: sha256:c0f32df6bb1b03862a20bd3ebdcc5b6ec3588e67f48caad6da64e523b4fb590b
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"

    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small thing for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the small thing.\n"
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
        "- Initial.\n"
    )
    _write(comp / "component.md", component_md)

    filler = " ".join("filler" + str(i) for i in range(600))
    long_text = (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST do the long thing. "
        + filler
        + "\n"
    )
    _write(comp / "requirements" / "R-FOO-001.md", long_text)

    short_text = (
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — The component MUST do the short thing.\n"
    )
    _write(comp / "requirements" / "R-FOO-002.md", short_text)

    ac1 = (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
    )
    _write(comp / "acceptance" / "AC-FOO-001.md", ac1)

    ac2 = (
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: compiled\n"
        "\n"
        "Given another thing\n"
        "When it runs\n"
        "Then it also works\n"
    )
    _write(comp / "acceptance" / "AC-FOO-002.md", ac2)

    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    total_words = 0
    for p in comp.rglob("*.md"):
        total_words += len(p.read_text(encoding="utf-8").split())
    assert total_words < 4000

    return len(long_text.split()), len(short_text.split())


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def test_ac_size_003_per_file_word_count(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    long_count, short_count = _build_fixture(repo_root)
    assert long_count > 500
    assert short_count < 250

    findings = size_checker.check(repo_root)

    long_rel = "specs/components/foo/requirements/R-FOO-001.md"
    short_rel = "specs/components/foo/requirements/R-FOO-002.md"

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    long_findings = [f for f in size3 if _norm(field(f, "file")) == long_rel]
    assert len(long_findings) >= 1, findings
    fail_findings = [f for f in long_findings if field(f, "severity") == "fail"]
    assert len(fail_findings) >= 1, long_findings
    assert any(str(long_count) in str(field(f, "message")) for f in fail_findings), fail_findings
    for f in fail_findings:
        assert isinstance(field(f, "line"), int)

    short_findings = [f for f in size3 if _norm(field(f, "file")) == short_rel]
    assert short_findings == [], short_findings

    size1 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    assert size1 == [], size1