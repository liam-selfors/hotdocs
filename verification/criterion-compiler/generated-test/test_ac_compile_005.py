import os
from pathlib import Path

import pytest

import criterion_compiler


COMPONENT_SLUG = "widget"
COMPONENT_ID = "comp-widget"
COMPILED_ID = "AC-WIDGET-001"
JUDGE_ID = "AC-WIDGET-002"


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path) -> Path:
    comp_dir = root / "specs" / "components" / COMPONENT_SLUG

    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: {COMPONENT_ID}\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "A tiny synthetic component used as a compiler fixture.\n",
    )

    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n"
        "**R-WIDGET-001** — `echo` MUST return its input text.\n",
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n"
        "**R-WIDGET-002** — The widget SHOULD feel pleasant to use.\n",
    )

    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "echo(text: str) -> str\n"
        "```\n"
        "\n"
        "`echo` returns its input.\n",
    )

    _write(
        comp_dir / "acceptance" / f"{COMPILED_ID}.md",
        f"# {COMPILED_ID}\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is \"hello\"\n"
        "When echo is invoked with {\"text\": payload}\n"
        "Then result equals \"hello\"\n"
        "```\n",
    )

    _write(
        comp_dir / "acceptance" / f"{JUDGE_ID}.md",
        f"# {JUDGE_ID}\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a user reads the widget documentation\n"
        "When they try to use the widget for the first time\n"
        "Then the experience feels pleasant and unsurprising\n"
        "```\n",
    )

    return comp_dir


def _resolve(repo_root: Path, file_value) -> Path:
    p = Path(str(file_value))
    if p.is_absolute():
        return p
    return repo_root / p


@pytest.fixture
def repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    return repo_root


def test_compiled_emitted_and_llm_judge_skipped_not_errored(repo):
    out_dir = repo / "verification" / COMPONENT_SLUG / "compiled"

    report = criterion_compiler.compile(
        COMPONENT_ID, repo, target="pytest", out_dir=out_dir
    )

    outputs = _get(report, "outputs") or []
    summary = _get(report, "summary") or {}

    # The compiled criterion produced an emitted test file.
    compiled_entries = [
        o for o in outputs if _get(o, "criterion_id") == COMPILED_ID
    ]
    assert len(compiled_entries) == 1, outputs
    entry = compiled_entries[0]
    assert _get(entry, "status") == "compiled", entry
    file_value = _get(entry, "file")
    assert file_value, entry
    emitted = _resolve(repo, file_value)
    assert emitted.is_file(), f"emitted test file missing: {emitted}"
    assert emitted.name == "test_ac_widget_001.py"
    assert emitted.read_text(encoding="utf-8").strip()

    # The llm-judge criterion is never reported as an error.
    judge_errors = [
        o
        for o in outputs
        if _get(o, "criterion_id") == JUDGE_ID and _get(o, "status") == "error"
    ]
    assert judge_errors == [], judge_errors
    assert not any(_get(o, "status") == "error" for o in outputs), outputs

    # The llm-judge criterion is not compiled into a test file either.
    assert not any(
        _get(o, "criterion_id") == JUDGE_ID and _get(o, "status") == "compiled"
        for o in outputs
    ), outputs
    assert not (out_dir / "test_ac_widget_002.py").exists()

    # It appears in summary.skipped_non_compiled_kind.
    skipped = _get(summary, "skipped_non_compiled_kind")
    assert skipped is not None, summary
    if isinstance(skipped, (list, tuple, set)):
        assert JUDGE_ID in skipped, skipped
        assert COMPILED_ID not in skipped, skipped
    else:
        assert skipped == 1, summary

    assert _get(summary, "errors") == 0, summary
    assert _get(summary, "compiled") == 1, summary


def test_cli_exits_zero_when_only_non_compiled_kind_is_skipped(repo):
    out_dir = repo / "verification" / COMPONENT_SLUG / "compiled"
    cwd = os.getcwd()
    try:
        os.chdir(repo)
        code = criterion_compiler.main(
            [
                COMPONENT_ID,
                "--target=pytest",
                f"--out={out_dir}",
                f"--repo-root={repo}",
            ]
        )
    finally:
        os.chdir(cwd)

    assert code == 0
    assert (out_dir / "test_ac_widget_001.py").is_file()
    assert not (out_dir / "test_ac_widget_002.py").exists()