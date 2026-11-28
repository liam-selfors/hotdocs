# hotdocs-criterion: sha256:2f4fa60cc158681a45b990e99309b97888c0abd1bfef72b06a98196afb8938f5
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "big"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-big\n"
        "title: Big\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/big/\n"
        "---\n"
        "\n"
        "# Big\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component with a lot of generated code.\n",
    )
    write(
        comp_dir / "requirements" / "R-BIG-001.md",
        "# R-BIG-001\n"
        "\n"
        "**R-BIG-001** — The component MUST do one thing.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-BIG-001.md",
        "# AC-BIG-001\n"
        "\n"
        "Covers: R-BIG-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the component\n"
        "When it runs\n"
        "Then it does one thing\n"
        "```\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "do_thing() -> None\n"
        "```\n",
    )

    # Generated code: 1600 counted lines, plus blank and comment lines
    # that must not count.
    source = "# generated module header comment\n\n"
    for i in range(1600):
        source = source + "value_" + str(i) + " = " + repr(i) + "\n"
        if i % 100 == 0:
            source = source + "\n    # an indented comment line\n"
    write(repo_root / "gen" / "big" / "big.py", source)


def test_ac_size_001_generated_code_loc_over_fail_threshold(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001"
        and field(f, "severity") == "fail"
        and "generated_code_loc" in field(f, "message")
    ]
    assert matching, (
        "expected a fail-severity R-SIZE-001 finding naming generated_code_loc, got: "
        + repr(findings)
    )
    message = field(matching[0], "message")
    assert message.startswith("big: generated_code_loc is "), message
    assert "above the fail threshold of 1500" in message, message