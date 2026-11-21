# hotdocs-criterion: sha256:0a4b7595c9eae58cf47ae6c48d0704a6271fe9612f18727d539458f955e259e4
from pathlib import Path

import criterion_compiler


SLUG = "foo-widget"
COMPONENT_ID = "comp-" + SLUG


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Foo Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** - The widget MUST bind a payload.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** - The widget MUST read pleasantly.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nadd(a, b) -> int\n```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is 1\n"
        "Then status equals 1\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget documentation\n"
        "When a reviewer reads it\n"
        "Then it reads pleasantly and clearly\n"
        "```\n",
    )


def test_llm_judge_criterion_is_skipped_not_errored(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    out_dir = repo_root / "verification" / SLUG / "compiled"

    report = criterion_compiler.compile(COMPONENT_ID, repo_root, "pytest", out_dir)

    outputs = list(field(report, "outputs"))
    summary = field(report, "summary")

    # The compiled criterion produced an emitted test file.
    compiled_entries = [
        o for o in outputs if field(o, "criterion_id") == "AC-FOO-001"
    ]
    assert len(compiled_entries) == 1, outputs
    entry = compiled_entries[0]
    assert field(entry, "status") == "compiled", entry
    emitted = Path(field(entry, "file"))
    if not emitted.is_absolute():
        emitted = repo_root / emitted
    assert emitted.is_file(), emitted
    assert emitted.name == "test_ac_foo_001.py"

    # The llm-judge criterion is not an error.
    for o in outputs:
        if field(o, "criterion_id") == "AC-FOO-002":
            assert field(o, "status") != "error", o
    assert not any(field(o, "status") == "error" for o in outputs), outputs
    assert field(summary, "errors") == 0, summary
    assert field(summary, "compiled") == 1, summary

    # The llm-judge criterion appears in skipped_non_compiled_kind.
    skipped = field(summary, "skipped_non_compiled_kind")
    if isinstance(skipped, (list, tuple, set)):
        ids = [s if isinstance(s, str) else field(s, "criterion_id") for s in skipped]
        assert "AC-FOO-002" in ids, skipped
        assert "AC-FOO-001" not in ids, skipped
    else:
        assert skipped == 1, summary