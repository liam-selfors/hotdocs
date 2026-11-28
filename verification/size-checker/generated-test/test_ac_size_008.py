# hotdocs-criterion: sha256:6561f774dda03494648589f527a03f898a51f177e8c04170ea4970f4e79e7a92
import re
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
        "# Glossary\n\n- **Widget** — a small thing used in tests.\n",
    )

    comp = specs / "components" / "big"
    write(
        comp / "component.md",
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
        "A deliberately large component used to exercise size caps.\n",
    )

    for i in range(1, 22):
        rid = "R-BIG-" + str(i).zfill(3)
        write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** — The component MUST do thing "
            + str(i) + ".\n",
        )

    write(
        comp / "acceptance" / "AC-BIG-001.md",
        "# AC-BIG-001\n"
        "\n"
        "Covers: R-BIG-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does thing 1\n"
        "```\n",
    )

    # 8100 words of prose, no fenced block
    prose_lines = []
    for _ in range(810):
        prose_lines.append(" ".join(["lorem"] * 10))
    write(
        comp / "interface" / "library.md",
        "# Library\n\n" + "\n".join(prose_lines) + "\n",
    )

    # 801 code lines, 40 comment lines (after leading spaces), 40 blank lines
    code_lines = []
    for i in range(801):
        code_lines.append("v" + str(i) + " = " + str(i))
    for i in range(40):
        code_lines.append("    # comment " + str(i))
    for _ in range(40):
        code_lines.append("")
    write(repo_root / "gen" / "big" / "big.py", "\n".join(code_lines) + "\n")


def test_ac_size_008(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    big = [f for f in size001 if str(field(f, "message")).startswith("big: ")]

    fails = [f for f in big if field(f, "severity") == "fail"]
    assert fails == [], fails

    warns = [f for f in big if field(f, "severity") == "warn"]
    messages = [field(f, "message") for f in warns]

    assert (
        "big: requirement_count is 21, above the warn threshold of 20 "
        "(specs/architecture/size-caps.md)"
    ) in messages, messages
    assert (
        "big: generated_code_loc is 801, above the warn threshold of 800 "
        "(specs/architecture/size-caps.md)"
    ) in messages, messages

    def value_for(dimension, limit):
        pattern = re.compile(
            r"^big: " + re.escape(dimension)
            + r" is (\d+), above the warn threshold of "
            + re.escape(str(limit))
            + r" \(specs/architecture/size-caps\.md\)$"
        )
        for m in messages:
            match = pattern.match(m)
            if match:
                return int(match.group(1))
        return None

    gw = value_for("generator_words", 8000)
    assert gw is not None, messages
    assert gw > 8000

    cw = value_for("criterion_words_max", 6000)
    assert cw is not None, messages
    assert cw > 6000

    for f in warns:
        assert isinstance(field(f, "line"), int)