import textwrap
from pathlib import Path

import criterion_compiler


NEW_VERSION = "criterion-compiler@1.1.0"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "widget"
    _write(
        comp_dir / "component.md",
        """
        ---
        id: comp-widget
        title: Widget
        status: draft
        owners: [alice]
        depends_on: []
        sealed: true
        source_path: legacy/widget
        ---

        # Widget

        A synthetic fixture component.
        """,
    )
    _write(
        comp_dir / "constraints.md",
        """
        # Constraints

        None.
        """,
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        """
        # R-WIDGET-001

        **R-WIDGET-001** — `echo` MUST return its input text as `value`.
        """,
    )
    _write(
        comp_dir / "interface" / "library.md",
        """
        # Library

        ```
        echo(text: str) -> dict
        ```
        """,
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        """
        # AC-WIDGET-001

        Covers: R-WIDGET-001
        Kind: compiled

        ```gherkin
        Given a payload is "hi"
        When echo is invoked with {"text": payload}
        Then value equals "hi"
        ```
        """,
    )


def _compile(repo_root: Path, out_dir: Path):
    try:
        return criterion_compiler.compile(
            "comp-widget", repo_root, target="pytest", out_dir=out_dir
        )
    except Exception:
        return criterion_compiler.compile(
            "widget", repo_root, target="pytest", out_dir=out_dir
        )


def test_gate_version_follows_module_attribute(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    original_version = criterion_compiler.GATE_VERSION
    assert original_version != NEW_VERSION

    first_report = _compile(repo_root, tmp_path / "out1")
    first_version = _get(first_report, "gate_version")
    assert first_version == original_version

    monkeypatch.setattr(criterion_compiler, "GATE_VERSION", NEW_VERSION)

    second_report = _compile(repo_root, tmp_path / "out2")
    second_version = _get(second_report, "gate_version")

    assert second_version == NEW_VERSION
    assert second_version != first_version