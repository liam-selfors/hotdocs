# hotdocs-criterion: sha256:c17290a5bbe1976592a977a71a39e1c870738bbd539f17645b7bac5eda2a1c8a
from pathlib import Path

import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FENCE = "```"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [widget-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A tiny fixture component.\n",
    )
    write(
        comp / "requirements" / "R-WID-001.md",
        "# R-WID-001\n"
        "\n"
        "**R-WID-001** \u2014 The widget MUST be makeable.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        + FENCE + "\n"
        "make_widget(name: str) -> dict\n"
        + FENCE + "\n",
    )
    acceptance_lines = [
        "# AC-WID-001",                 # line 1
        "",                             # line 2
        "Covers: R-WID-001",            # line 3
        "Kind: compiled",               # line 4
        "",                             # line 5
        FENCE + "gherkin",              # line 6
        'Given a payload is "hi"',      # line 7
        "When a wizard appears",        # line 8  <- unmatched step
        "Then name equals " + '"hi"',   # line 9
        FENCE,                          # line 10
        "",
    ]
    acc = comp / "acceptance" / "AC-WID-001.md"
    write(acc, "\n".join(acceptance_lines))
    return acc


def run_compile(repo_root, out_dir):
    try:
        return criterion_compiler.compile("comp-widget", repo_root, "pytest", out_dir)
    except Exception:
        return criterion_compiler.compile("widget", repo_root, "pytest", out_dir)


def test_unmatched_step_is_located_compile_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    acc = build_fixture(repo_root)
    out_dir = tmp_path / "out"

    report = run_compile(repo_root, out_dir)

    outputs = list(field(report, "outputs"))
    entries = [o for o in outputs if field(o, "criterion_id") == "AC-WID-001"]
    assert len(entries) == 1, "criterion must appear in the report, not be silently skipped: " + repr(outputs)
    entry = entries[0]

    assert field(entry, "status") == "error"

    file_value = Path(field(entry, "file"))
    if not file_value.is_absolute():
        file_value = repo_root / file_value
    assert file_value.resolve() == acc.resolve()

    message = field(entry, "message")
    assert message.startswith("line 8: "), message
    assert "'When a wizard appears'" in message, message
    assert "does not match any recognized template" in message, message

    summary = field(report, "summary")
    assert field(summary, "errors") >= 1