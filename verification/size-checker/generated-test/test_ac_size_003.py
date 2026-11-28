# hotdocs-criterion: sha256:d05eea7db7ffd9c0fafcbd0b27368f72070b405b5342c63bface4c1d9bffbe31
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    comp = specs / "components" / "foo"
    _write(
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
        "A small fixture component used to exercise per-file word caps.\n",
    )

    long_req = (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST do the thing, described at length: "
        + " ".join(["word"] * 520)
        + "\n"
    )
    _write(comp / "requirements" / "R-FOO-001.md", long_req)

    short_req = (
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — The component MUST do a second, small thing.\n"
    )
    _write(comp / "requirements" / "R-FOO-002.md", short_req)

    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a second thing\n"
        "When it runs\n"
        "Then it also works\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "do_thing(x: int) -> int\n"
        "```\n",
    )
    return len(long_req.split()), len(short_req.split())


def test_ac_size_003_per_file_word_cap(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    long_words, short_words = _build_fixture(repo_root)
    assert long_words > 500
    assert short_words < 250

    findings = size_checker.check(repo_root)

    long_rel = "specs/components/foo/requirements/R-FOO-001.md"
    short_rel = "specs/components/foo/requirements/R-FOO-002.md"

    def norm(p):
        return str(p).replace("\\", "/")

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    long_findings = [f for f in size3 if norm(field(f, "file")) == long_rel]
    expected_message = (
        long_rel
        + " has "
        + str(long_words)
        + " words, above the per-file fail threshold of 500"
    )
    fail_findings = [f for f in long_findings if field(f, "severity") == "fail"]
    assert fail_findings, (
        "expected a fail-severity R-SIZE-003 finding for the long file; got "
        + repr(findings)
    )
    assert any(field(f, "message") == expected_message for f in fail_findings), (
        "expected message " + repr(expected_message) + "; got " + repr(fail_findings)
    )
    for f in fail_findings:
        assert isinstance(field(f, "line"), int)
        assert str(long_words) in field(f, "message")

    short_findings = [f for f in size3 if norm(field(f, "file")) == short_rel]
    assert short_findings == [], (
        "expected no R-SIZE-003 finding for the short file; got " + repr(short_findings)
    )

    word_size1 = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001" and "words" in field(f, "message")
    ]
    assert word_size1 == [], (
        "expected no R-SIZE-001 word finding; got " + repr(word_size1)
    )