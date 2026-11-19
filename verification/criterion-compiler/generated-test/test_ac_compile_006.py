# hotdocs-criterion: sha256:88c1e6def115f4d190458b8928702294cfedd1baf45038d472524b9755053e7c
import hashlib
from pathlib import Path

import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"
    _write(
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
        "A tiny fixture component.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — `make` MUST return a result whose `total` is the given value.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make(value: int) -> Result\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is 3\n"
        "When make is invoked with {\"value\": payload}\n"
        "Then total equals 3\n"
        "```\n",
    )


def _snapshot(root):
    snap = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            snap[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


def _run_compile(repo_root):
    try:
        return criterion_compiler.compile("comp-widget", repo_root)
    except Exception:
        return criterion_compiler.compile("widget", repo_root)


def test_compiled_output_written_under_verification_never_under_specs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    before = _snapshot(repo_root)
    specs_before = {k: v for k, v in before.items() if k.startswith("specs/")}

    report = _run_compile(repo_root)

    outputs = field(report, "outputs")
    summary = field(report, "summary")
    assert len(outputs) >= 1
    for entry in outputs:
        assert field(entry, "status") == "compiled", entry
    assert summary["errors"] == 0
    assert summary["compiled"] >= 1

    expected_dir = (repo_root / "verification" / "widget" / "compiled").resolve()

    for entry in outputs:
        f = Path(field(entry, "file"))
        abs_f = f if f.is_absolute() else repo_root / f
        abs_f = abs_f.resolve()
        assert abs_f.parent == expected_dir, abs_f
        assert abs_f.is_file(), abs_f
        assert "specs" not in abs_f.relative_to(repo_root.resolve()).parts

    assert (expected_dir / "test_ac_widget_001.py").is_file()

    after = _snapshot(repo_root)

    # Nothing under specs/ was added, removed or changed.
    specs_after = {k: v for k, v in after.items() if k.startswith("specs/")}
    assert specs_after == specs_before

    # Every new or changed file lies under verification/widget/compiled/.
    changed = [k for k, v in after.items() if before.get(k) != v]
    assert changed, "compile wrote no files"
    for rel in changed:
        assert rel.startswith("verification/widget/compiled/"), rel
        assert not rel.startswith("specs/"), rel