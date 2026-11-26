# hotdocs-criterion: sha256:6690325761601a1e9b28d02c81241ed69cafd4273ac8d96284f9f924c6fd23eb
"""AC-SIZE-001: a component whose generated-code LOC estimate exceeds 1500
yields a fail-severity R-SIZE-001 finding naming `generated_code_loc`."""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"

    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a fixture term.\n",
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
        "A small fixture component used to exercise the size checker.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — The component MUST do one small thing.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does one small thing\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "do_thing() -> None\n"
        "```\n",
    )

    # 1600 non-blank, non-comment lines of generated code: above the
    # 1500 LOC hard-fail threshold.
    lines = []
    for i in range(1600):
        lines.append("x_" + str(i) + " = " + repr(i))
    write(repo_root / "gen" / "foo" / "foo.py", "\n".join(lines) + "\n")


def test_ac_size_001_generated_code_loc_over_fail_threshold(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    loc_fail = [
        f
        for f in size_001
        if field(f, "severity") == "fail"
        and "generated_code_loc" in field(f, "message")
    ]
    assert loc_fail, (
        "expected a fail-severity R-SIZE-001 finding naming generated_code_loc; got "
        + repr(findings)
    )