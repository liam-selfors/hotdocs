# hotdocs-criterion: sha256:67aab5ce8211ef956001b986195637caec91df667533b4ac8beba7f1e56b1952
import os
from pathlib import Path

import criterion_compiler


COMPONENT_ID = "comp-widget"
SLUG = "widget"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "**R-WIDGET-001** — `do_thing` MUST return a result whose `value` equals its input.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "do_thing(x: int) -> dict\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is 5\n"
        "When do_thing is invoked with {\"x\": payload}\n"
        "Then value equals 5\n"
        "```\n",
    )


def compiled_dir(repo_root):
    return repo_root / "verification" / SLUG / "compiled"


def files_under(directory):
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file())


def test_unsupported_target_rejected_and_pytest_output_is_target_independent(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    # --- Unsupported target: jest ---
    capsys.readouterr()
    code = criterion_compiler.main(
        [COMPONENT_ID, "--target=jest", "--repo-root", str(repo_root)]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "jest" in (captured.out + captured.err)
    assert files_under(compiled_dir(repo_root)) == []
    # Nothing written anywhere under verification/ either
    assert files_under(repo_root / "verification") == []

    # --- Supported target: pytest, compiled twice ---
    code1 = criterion_compiler.main(
        [COMPONENT_ID, "--target=pytest", "--repo-root", str(repo_root)]
    )
    assert code1 == 0
    out_file = compiled_dir(repo_root) / "test_ac_widget_001.py"
    assert out_file.is_file()
    first = out_file.read_bytes()
    assert len(first) > 0

    # A rejected jest run in between must not disturb pytest output
    capsys.readouterr()
    code_jest_again = criterion_compiler.main(
        [COMPONENT_ID, "--target=jest", "--repo-root", str(repo_root)]
    )
    captured = capsys.readouterr()
    assert code_jest_again == 2
    assert "jest" in (captured.out + captured.err)
    assert out_file.read_bytes() == first
    assert files_under(compiled_dir(repo_root)) == [out_file]

    code2 = criterion_compiler.main(
        [COMPONENT_ID, "--target=pytest", "--repo-root", str(repo_root)]
    )
    assert code2 == 0
    second = out_file.read_bytes()
    assert second == first
    assert files_under(compiled_dir(repo_root)) == [out_file]