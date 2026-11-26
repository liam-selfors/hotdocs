# hotdocs-criterion: sha256:3e2423efada13d372c643651e327b84f28d57ac59234c8a2955a865945bcb678
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
        "Foo does a small fixture job for testing size checks.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "Foo behaves simply.\n",
    )
    long_text = (
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST "
        + " ".join(["word"] * 520)
        + ".\n"
    )
    short_text = (
        "# R-FOO-002\n\n**R-FOO-002** — The component MUST do one short thing.\n"
    )
    write(comp / "requirements" / "R-FOO-001.md", long_text)
    write(comp / "requirements" / "R-FOO-002.md", short_text)
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: judged\n\n"
        "Given a thing, when it runs, then it works.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: judged\n\n"
        "Given a thing, when it runs, then it works.\n",
    )
    return long_text, short_text


def test_ac_size_003(tmp_path):
    repo_root = tmp_path
    long_text, short_text = build_fixture(repo_root)
    long_words = len(long_text.split())
    short_words = len(short_text.split())
    assert long_words > 500
    assert short_words < 250

    findings = size_checker.check(repo_root)

    long_rel = "specs/components/foo/requirements/R-FOO-001.md"
    short_rel = "specs/components/foo/requirements/R-FOO-002.md"

    def norm(p):
        return str(p).replace("\\", "/")

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    long_findings = [f for f in size3 if norm(field(f, "file")) == long_rel]
    assert long_findings, findings
    fail_findings = [f for f in long_findings if field(f, "severity") == "fail"]
    assert len(fail_findings) == 1, long_findings
    msg = field(fail_findings[0], "message")
    expected = (
        long_rel
        + " has "
        + str(long_words)
        + " words, above the per-file fail threshold of 500"
    )
    assert msg == expected
    assert str(long_words) in msg

    short_findings = [f for f in size3 if norm(field(f, "file")) == short_rel]
    assert short_findings == []

    size1_word = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001"
        and (
            "generator_words" in field(f, "message")
            or "criterion_words_max" in field(f, "message")
        )
    ]
    assert size1_word == []