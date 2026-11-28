# hotdocs-criterion: sha256:4f0d64d023519e1dc8df62351844ff97715064ad00ba58bde13dd61345104abe
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


MESSAGE_RE = re.compile(
    r"^big: (\w+) is (\d+), above the (warn|fail) threshold of (\d+) "
    r"\(specs/architecture/size-caps\.md\)$"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "big"

    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing.\n",
    )

    _write(
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
        "A big component used for size checking.\n",
    )

    for i in range(1, 22):
        rid = "R-BIG-" + str(i).zfill(3)
        _write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** — The component MUST do thing "
            + str(i) + ".\n",
        )

    _write(
        comp / "acceptance" / "AC-BIG-001.md",
        "# AC-BIG-001\n"
        "\n"
        "Covers: R-BIG-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )

    words = []
    for i in range(8100):
        words.append("prose" + str(i % 50))
    lines = []
    for start in range(0, len(words), 10):
        lines.append(" ".join(words[start:start + 10]))
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n" + "\n".join(lines) + "\n",
    )

    code_lines = []
    for i in range(801):
        code_lines.append("x_" + str(i) + " = " + str(i))
    for i in range(40):
        code_lines.append("    # comment " + str(i))
    for i in range(40):
        code_lines.append("")
    _write(repo_root / "gen" / "big" / "big.py", "\n".join(code_lines) + "\n")


def test_ac_size_008_big_component_warns_on_four_dimensions(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    big_findings = [
        f for f in size_001 if str(field(f, "message")).startswith("big: ")
    ]

    fails = [f for f in big_findings if field(f, "severity") == "fail"]
    assert fails == [], "unexpected fail R-SIZE-001 findings: " + repr(fails)

    values = {}
    for f in big_findings:
        assert field(f, "severity") == "warn"
        match = MESSAGE_RE.match(field(f, "message"))
        assert match is not None, "unexpected message: " + repr(field(f, "message"))
        dimension, value, severity, _limit = match.groups()
        assert severity == "warn"
        values[dimension] = int(value)

    assert values.get("requirement_count") == 21, repr(values)
    assert values.get("generated_code_loc") == 801, repr(values)
    assert "generator_words" in values, repr(values)
    assert values["generator_words"] > 8000
    assert "criterion_words_max" in values, repr(values)
    assert values["criterion_words_max"] > 6000