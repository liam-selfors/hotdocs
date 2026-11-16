import os
import tempfile
from pathlib import Path

import criterion_compiler


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "widget"
    _write(
        comp_dir / "component.md",
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
        "A synthetic component used to exercise criterion compilation.\n",
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — `echo` MUST return its input.\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "echo(value: str) -> dict\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is \"hi\"\n"
        "When echo is invoked with {\"value\": payload}\n"
        "Then value equals \"hi\"\n"
        "```\n",
    )


def _snapshot(root: Path) -> dict:
    snap = {}
    if not root.exists():
        return snap
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            snap[rel] = p.read_bytes()
    return snap


def _run_compile(repo_root: Path):
    last_exc = None
    for component_id in ("comp-widget", "widget"):
        try:
            report = criterion_compiler.compile(component_id, repo_root)
        except Exception as exc:  # try the other id form
            last_exc = exc
            continue
        outputs = _get(report, "outputs") or []
        if any(_get(o, "status") == "compiled" for o in outputs):
            return report
    if last_exc is not None:
        raise last_exc
    raise AssertionError("compile produced no successfully compiled output")


def test_compiled_output_written_under_verification_never_specs():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp).resolve()
        _build_fixture(repo_root)

        before_all = _snapshot(repo_root)
        before_specs = _snapshot(repo_root / "specs")

        report = _run_compile(repo_root)

        outputs = _get(report, "outputs") or []
        compiled = [o for o in outputs if _get(o, "status") == "compiled"]
        assert compiled, f"expected a successful compile, got outputs: {outputs!r}"
        errors = [o for o in outputs if _get(o, "status") == "error"]
        assert not errors, f"unexpected compile errors: {errors!r}"

        expected_dir = (repo_root / "verification" / "widget" / "compiled").resolve()
        specs_dir = (repo_root / "specs").resolve()

        # Every reported compiled file is under verification/widget/compiled/.
        for entry in compiled:
            file_value = _get(entry, "file")
            assert file_value, f"compiled entry missing file: {entry!r}"
            fpath = Path(file_value)
            if not fpath.is_absolute():
                fpath = repo_root / fpath
            fpath = fpath.resolve()
            assert fpath.parent == expected_dir, (
                f"compiled file {file_value!r} not directly under "
                f"verification/widget/compiled/"
            )
            assert specs_dir not in fpath.parents, (
                f"compiled file {file_value!r} written under specs/"
            )
            assert fpath.is_file(), f"compiled file {file_value!r} does not exist"

        # The expected deterministic test file exists.
        assert (expected_dir / "test_ac_widget_001.py").is_file()

        # Nothing under specs/ was created or modified.
        after_specs = _snapshot(repo_root / "specs")
        assert after_specs == before_specs, (
            "compile created or modified files under specs/: "
            f"{sorted(set(after_specs) ^ set(before_specs))}"
        )

        # Every newly written or changed file lives under verification/widget/compiled/.
        after_all = _snapshot(repo_root)
        changed = [
            rel
            for rel, data in after_all.items()
            if rel not in before_all or before_all[rel] != data
        ]
        assert changed, "compile wrote no files at all"
        for rel in changed:
            assert rel.startswith("verification/widget/compiled/"), (
                f"compile wrote {rel!r} outside verification/widget/compiled/"
            )
            assert not rel.startswith("specs/"), f"compile wrote {rel!r} under specs/"