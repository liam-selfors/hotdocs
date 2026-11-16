import os
import time
from pathlib import Path

import pytest

import criterion_compiler


SLUG = "widget-maker"
COMPONENT_ID = "comp-" + SLUG


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / SLUG

    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget-maker\n"
        "title: Widget Maker\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget_maker\n"
        "---\n"
        "\n"
        "# Widget Maker\n"
        "\n"
        "A synthetic component used to exercise criterion compilation.\n",
    )

    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** - make_widget MUST return a widget named as asked.\n",
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n"
        "\n"
        "**R-WIDGET-002** - A bound fixture MUST be observable.\n",
    )

    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget(name: str, size: int = 1) -> dict\n"
        "```\n"
        "\n"
        "Builds a widget.\n",
    )

    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is \"abc\"\n"
        "When make_widget is invoked with {\"name\": payload}\n"
        "Then name equals \"abc\"\n"
        "```\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a count is 3\n"
        "Then size equals 3\n"
        "```\n",
    )


def _compile(repo_root: Path, out_dir: Path):
    last_exc = None
    for cid in (COMPONENT_ID, SLUG):
        try:
            report = criterion_compiler.compile(cid, repo_root, out_dir=out_dir)
        except Exception as exc:  # try the other id form
            last_exc = exc
            continue
        outputs = _get(report, "outputs") or []
        if outputs:
            return cid, report
    if last_exc is not None:
        raise last_exc
    pytest.fail("compile produced no outputs for either component id form")


def _snapshot(out_dir: Path) -> dict:
    snap = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            st = os.stat(p)
            snap[str(p.relative_to(out_dir))] = (st.st_mtime_ns, p.read_bytes())
    return snap


def test_recompiling_unchanged_content_does_not_touch_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    out_dir = tmp_path / "out" / "compiled"

    cid, first_report = _compile(repo_root, out_dir)

    outputs = _get(first_report, "outputs") or []
    compiled = [o for o in outputs if _get(o, "status") == "compiled"]
    assert compiled, (
        "fixture expected to compile at least one criterion; outputs were: %r"
        % (outputs,)
    )

    before = _snapshot(out_dir)
    assert before, "first compile wrote no files under the --out directory"

    # Ensure any rewrite would be observable even on coarse-mtime filesystems.
    time.sleep(1.2)

    second_report = criterion_compiler.compile(cid, repo_root, out_dir=out_dir)
    second_outputs = _get(second_report, "outputs") or []
    assert second_outputs, "second compile returned no outputs"

    after = _snapshot(out_dir)

    for rel, (mtime_ns, content) in before.items():
        assert rel in after, "output file %s disappeared on recompile" % rel
        new_mtime_ns, new_content = after[rel]
        assert new_content == content, (
            "output file %s content changed on recompile of unchanged input" % rel
        )
        assert new_mtime_ns == mtime_ns, (
            "output file %s mtime changed on recompile of unchanged input "
            "(%d -> %d)" % (rel, mtime_ns, new_mtime_ns)
        )

    assert set(after) == set(before), (
        "set of output files changed on recompile: before=%r after=%r"
        % (sorted(before), sorted(after))
    )