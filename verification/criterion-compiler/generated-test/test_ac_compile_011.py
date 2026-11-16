import os
from pathlib import Path

import pytest

import criterion_compiler


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_FILENAME = "test_ac_widget_001.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path) -> Path:
    comp = root / "specs" / "components" / SLUG
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — `widget_fn` MUST echo its `text` argument back.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is \"hello\"\n"
        "When widget_fn is invoked with {\"text\": payload}\n"
        "Then text equals \"hello\"\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "widget_fn(text: str) -> dict\n"
        "```\n"
        "\n"
        "`widget_fn` returns an object whose `text` field echoes the input.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    return root


def _run_main(argv):
    try:
        code = criterion_compiler.main(argv)
    except SystemExit as exc:
        code = exc.code
    return code


def _files_under(directory: Path):
    if not directory.exists():
        return []
    return [p for p in directory.rglob("*") if p.is_file()]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _build_repo(root)
    monkeypatch.chdir(root)
    return root


def test_unsupported_target_jest_is_usage_error_and_writes_nothing(repo, capsys):
    default_out = repo / "verification" / SLUG / "compiled"
    assert _files_under(default_out) == []

    code = _run_main([COMPONENT_ID, "--target=jest", f"--repo-root={repo}"])
    captured = capsys.readouterr()

    assert code == 2, (
        f"expected exit code 2 for unsupported --target=jest, got {code!r}; "
        f"stdout={captured.out!r} stderr={captured.err!r}"
    )
    combined = (captured.out or "") + (captured.err or "")
    assert "jest" in combined, (
        "usage error must name the unsupported target 'jest'; "
        f"stdout={captured.out!r} stderr={captured.err!r}"
    )
    assert _files_under(default_out) == [], (
        "no output file may be written under verification/<component>/compiled/ "
        f"for an unsupported target; found {_files_under(default_out)!r}"
    )
    assert not (default_out / CRITERION_FILENAME).exists()


def test_unsupported_target_jest_with_explicit_out_writes_nothing(repo, tmp_path, capsys):
    out_dir = tmp_path / "jest_out"
    code = _run_main(
        [COMPONENT_ID, "--target=jest", f"--out={out_dir}", f"--repo-root={repo}"]
    )
    captured = capsys.readouterr()

    assert code == 2
    assert "jest" in ((captured.out or "") + (captured.err or ""))
    assert _files_under(out_dir) == []
    assert _files_under(repo / "verification" / SLUG / "compiled") == []


def test_pytest_target_compiles_and_is_byte_identical_across_runs(repo, capsys):
    out_file = repo / "verification" / SLUG / "compiled" / CRITERION_FILENAME

    code1 = _run_main([COMPONENT_ID, "--target=pytest", f"--repo-root={repo}"])
    captured1 = capsys.readouterr()
    assert code1 == 0, (
        f"expected exit 0 for --target=pytest, got {code1!r}; "
        f"stdout={captured1.out!r} stderr={captured1.err!r}"
    )
    assert out_file.is_file(), f"expected compiled output at {out_file}"
    first = out_file.read_bytes()
    assert first, "compiled output must not be empty"

    text = first.decode("utf-8")
    assert "widget_fn" in text
    assert "\"hello\"" in text

    code2 = _run_main([COMPONENT_ID, "--target=pytest", f"--repo-root={repo}"])
    captured2 = capsys.readouterr()
    assert code2 == 0, (
        f"second compile failed: {code2!r}; stdout={captured2.out!r} stderr={captured2.err!r}"
    )
    assert out_file.is_file()
    second = out_file.read_bytes()
    assert first == second, "recompiling with unchanged inputs must be byte-identical"


def test_failed_jest_run_does_not_affect_subsequent_pytest_output(repo, tmp_path, capsys):
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"

    code_a = _run_main(
        [COMPONENT_ID, "--target=pytest", f"--out={out_a}", f"--repo-root={repo}"]
    )
    capsys.readouterr()
    assert code_a == 0
    file_a = out_a / CRITERION_FILENAME
    assert file_a.is_file()

    code_jest = _run_main([COMPONENT_ID, "--target=jest", f"--repo-root={repo}"])
    capsys.readouterr()
    assert code_jest == 2

    code_b = _run_main([COMPONENT_ID, f"--out={out_b}", f"--repo-root={repo}"])
    capsys.readouterr()
    assert code_b == 0
    file_b = out_b / CRITERION_FILENAME
    assert file_b.is_file()

    assert file_a.read_bytes() == file_b.read_bytes(), (
        "default target and explicit --target=pytest must emit identical bytes"
    )


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def test_library_compile_pytest_is_deterministic(repo, tmp_path):
    out_1 = tmp_path / "lib_out_1"
    out_2 = tmp_path / "lib_out_2"

    report1 = criterion_compiler.compile(COMPONENT_ID, repo, target="pytest", out_dir=out_1)
    report2 = criterion_compiler.compile(COMPONENT_ID, repo, target="pytest", out_dir=out_2)

    for report in (report1, report2):
        summary = _get(report, "summary")
        assert summary is not None
        compiled = _get(summary, "compiled")
        errors = _get(summary, "errors")
        assert compiled == 1, f"expected 1 compiled criterion, got summary={summary!r}"
        assert errors == 0, f"expected 0 errors, got summary={summary!r}"
        outputs = _get(report, "outputs") or []
        statuses = [_get(o, "status") for o in outputs]
        assert statuses == ["compiled"], f"unexpected outputs: {outputs!r}"
        ids = [_get(o, "criterion_id") for o in outputs]
        assert ids == ["AC-WIDGET-001"]

    f1 = out_1 / CRITERION_FILENAME
    f2 = out_2 / CRITERION_FILENAME
    assert f1.is_file()
    assert f2.is_file()
    assert f1.read_bytes() == f2.read_bytes()