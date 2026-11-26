# hotdocs-criterion: sha256:03ab32c3136de75991ab752a452ee455c6a0f10e8da24a937e9bf3c0bbae880f
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"

    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing used in tests.\n",
    )

    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small thing for tests.\n"
    )
    _write(comp / "component.md", component_md)

    _write(
        comp / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do the first small thing.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "**R-FOO-002** — Foo MUST do the second small thing.\n",
    )

    # "Covers:" and "R-FOO-001" are 2 tokens; pad to exactly 300 tokens.
    first_text = "Covers: R-FOO-001\n" + " ".join(["word"] * 298) + "\n"
    # "Covers:" and "R-FOO-002" are 2 tokens; pad to exactly 520 tokens.
    second_text = "Covers: R-FOO-002\n" + " ".join(["word"] * 518) + "\n"
    assert len(first_text.split()) == 300
    assert len(second_text.split()) == 520

    _write(comp / "acceptance" / "AC-FOO-001.md", first_text)
    _write(comp / "acceptance" / "AC-FOO-002.md", second_text)


def test_ac_size_007_per_file_warn_and_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    first_file = "specs/components/foo/acceptance/AC-FOO-001.md"
    second_file = "specs/components/foo/acceptance/AC-FOO-002.md"

    by_file = {}
    for f in size3:
        by_file.setdefault(field(f, "file"), []).append(f)

    assert set(by_file) == {first_file, second_file}, size3
    assert len(by_file[first_file]) == 1, size3
    assert len(by_file[second_file]) == 1, size3

    first = by_file[first_file][0]
    second = by_file[second_file][0]

    assert field(first, "severity") == "warn"
    assert field(second, "severity") == "fail"

    first_msg = field(first, "message")
    second_msg = field(second, "message")
    assert "300" in first_msg
    assert "520" in second_msg
    assert first_msg == (
        first_file + " has 300 words, above the per-file warn threshold of 250"
    )
    assert second_msg == (
        second_file + " has 520 words, above the per-file fail threshold of 500"
    )

    assert isinstance(field(first, "line"), int)
    assert isinstance(field(second, "line"), int)

    # Findings come in the corpus's sorted file-path order.
    files_in_order = [field(f, "file") for f in size3]
    assert files_in_order == [first_file, second_file]