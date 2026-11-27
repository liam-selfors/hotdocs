# hotdocs-criterion: sha256:b21f5e238e1875a2b30aabbe123095ee23ed0267e8696cccf7b1c1bcd4acb844
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, loc):
    comp = repo_root / "specs" / "components" / "foo"
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
        "Foo does one small thing.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST return one.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo runs\n"
        "Then it returns one\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo() -> int\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test component.\n",
    )

    lines = []
    for i in range(loc):
        lines.append("x_" + str(i) + " = " + repr(i))
        if i % 100 == 0:
            lines.append("")
            lines.append("# a comment line that never counts")
    write(repo_root / "gen" / "foo" / "foo.py", "\n".join(lines) + "\n")


def test_ac_size_001_generated_code_loc_over_fail_threshold(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, 1600)

    findings = size_checker.check(repo_root)

    matches = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001"
        and field(f, "severity") == "fail"
        and "generated_code_loc" in field(f, "message")
    ]
    assert matches, "no fail R-SIZE-001 finding naming generated_code_loc: " + repr(findings)
    message = field(matches[0], "message")
    assert message.startswith("foo: generated_code_loc is 1600"), message
    assert "above the fail threshold of 1500" in message, message