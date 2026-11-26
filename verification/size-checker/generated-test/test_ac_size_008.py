# hotdocs-criterion: sha256:4998d399f60ecb7fa975dae989b89d787b88616d00c65b83e4fc8ac41423f18f
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


MSG_RE = re.compile(
    r"^big: (?P<dim>\w+) is (?P<value>-?\d+), above the (?P<sev>warn|fail) threshold of (?P<limit>\d+) \(specs/architecture/size-caps\.md\)$"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\nCanonical vocabulary.\n\n- **Widget** — a small thing used in tests.\n",
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
        "Big is a deliberately oversized fixture component used to exercise size caps.\n",
    )
    for i in range(1, 22):
        rid = "R-BIG-" + str(i).zfill(3)
        write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** — The component MUST do thing number "
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
        "Given a big component\n"
        "When it runs\n"
        "Then it does thing number 1\n"
        "```\n",
    )
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
    lines = []
    count = 0
    while count < 8100:
        line_words = []
        for w in words:
            if count >= 8100:
                break
            line_words.append(w)
            count += 1
        lines.append(" ".join(line_words))
    write(
        comp / "interface" / "library.md",
        "\n".join(lines) + "\n",
    )
    assert sum(len(l.split()) for l in lines) == 8100

    py_lines = []
    for i in range(801):
        py_lines.append("x" + str(i) + " = " + str(i))
    for i in range(40):
        py_lines.append("    # comment " + str(i))
    for i in range(40):
        py_lines.append("")
    write(repo_root / "gen" / "big" / "big.py", "\n".join(py_lines) + "\n")


def test_ac_size_008(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    big = [f for f in size001 if str(field(f, "message")).startswith("big: ")]

    fails = [f for f in big if field(f, "severity") == "fail"]
    assert fails == [], [field(f, "message") for f in fails]

    values = {}
    for f in big:
        assert field(f, "severity") == "warn"
        m = MSG_RE.match(field(f, "message"))
        assert m is not None, field(f, "message")
        assert m.group("sev") == "warn"
        values[m.group("dim")] = int(m.group("value"))

    assert values.get("requirement_count") == 21, values
    assert values.get("generated_code_loc") == 801, values
    assert "generator_words" in values, values
    assert values["generator_words"] > 8000, values
    assert "criterion_words_max" in values, values
    assert values["criterion_words_max"] > 6000, values