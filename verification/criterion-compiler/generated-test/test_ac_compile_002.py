"""AC-COMPILE-002 (covers R-COMPILE-002).

Given an acceptance/ step that references a function name not declared in
the paired component's interface/ contract, when compile-criteria runs, the
CompileReport marks that criterion status: error, naming the unresolved
reference.
"""

import os
from pathlib import Path

import pytest

import criterion_compiler


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


# ---------------------------------------------------------------------------
# Synthetic fixture corpus
# ---------------------------------------------------------------------------

SLUG = "widget"
COMPONENT_ID = "comp-widget"
MISSING_FN = "missing_fn"
KNOWN_FN = "known_fn"

COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [test-owner]
depends_on: []
sealed: true
source_path: legacy/widget
---

# Widget

A tiny synthetic component used as a compiler fixture.
"""

REQUIREMENT_MD = """# R-WIDGET-001

**R-WIDGET-001** — The widget MUST expose `known_fn`.
"""

LIBRARY_MD = """# Library

```
known_fn(x: int) -> int
```

`known_fn` returns its argument.
"""

ACCEPTANCE_LINES = [
    "# AC-WIDGET-001",
    "",
    "Covers: R-WIDGET-001",
    "Kind: compiled",
    "",
    "```gherkin",
    "Given a payload is 1",
    'When missing_fn is invoked with {"x": 1}',
    "Then value equals 1",
    "```",
    "",
]
ACCEPTANCE_MD = "\n".join(ACCEPTANCE_LINES)
# 1-based line number of the offending step within the acceptance file.
OFFENDING_LINE = ACCEPTANCE_LINES.index('When missing_fn is invoked with {"x": 1}') + 1


def _build_repo(root: Path) -> Path:
    comp_dir = root / "specs" / "components" / SLUG
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp_dir / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (comp_dir / "requirements" / "R-WIDGET-001.md").write_text(REQUIREMENT_MD, encoding="utf-8")
    (comp_dir / "interface" / "library.md").write_text(LIBRARY_MD, encoding="utf-8")
    (comp_dir / "acceptance" / "AC-WIDGET-001.md").write_text(ACCEPTANCE_MD, encoding="utf-8")
    return root


def _run_compile(repo_root: Path, out_dir: Path):
    """Run compile() with the canonical comp-<slug> id, falling back to the bare slug."""
    last_exc = None
    for cid in (COMPONENT_ID, SLUG):
        try:
            report = criterion_compiler.compile(cid, repo_root, target="pytest", out_dir=out_dir)
        except Exception as exc:  # pragma: no cover - fallback path
            last_exc = exc
            continue
        outputs = _get(report, "outputs") or []
        if any(_get(o, "criterion_id") == "AC-WIDGET-001" for o in outputs):
            return report
        last_exc = AssertionError(f"no output entry for AC-WIDGET-001 in {outputs!r}")
    raise AssertionError(f"compile() never reported AC-WIDGET-001: {last_exc!r}")


# ---------------------------------------------------------------------------
# compile() — the full compile-criteria path
# ---------------------------------------------------------------------------


def test_compile_marks_unresolved_function_reference_as_error(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")
    out_dir = tmp_path / "out"

    report = _run_compile(repo_root, out_dir)
    outputs = _get(report, "outputs") or []
    entries = [o for o in outputs if _get(o, "criterion_id") == "AC-WIDGET-001"]
    assert len(entries) == 1, outputs
    entry = entries[0]

    assert _get(entry, "status") == "error", entry
    assert _get(entry, "covers") == "R-WIDGET-001", entry

    message = _get(entry, "message")
    assert isinstance(message, str) and message, entry
    assert MISSING_FN in message, message
    assert "does not resolve" in message, message
    assert message.startswith(f"line {OFFENDING_LINE}: "), message

    file_field = _get(entry, "file")
    assert isinstance(file_field, str) and file_field, entry
    assert file_field.replace(os.sep, "/").endswith("acceptance/AC-WIDGET-001.md"), file_field

    summary = _get(report, "summary") or {}
    errors = _get(summary, "errors")
    assert isinstance(errors, int) and errors >= 1, summary
    assert _get(report, "gate_version") == "criterion-compiler@1.0.0"


def test_cli_exits_1_on_unresolved_function_reference(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")
    out_dir = tmp_path / "out"

    codes = []
    for cid in (COMPONENT_ID, SLUG):
        code = criterion_compiler.main(
            [cid, "--target=pytest", f"--out={out_dir}", f"--repo-root={repo_root}"]
        )
        codes.append(code)
        if code != 2:
            break
    assert codes[-1] == 1, codes


# ---------------------------------------------------------------------------
# compile_criterion() — the per-criterion primitive compile() uses
# ---------------------------------------------------------------------------


def _surface():
    return criterion_compiler.InterfaceSurface(
        functions={KNOWN_FN: ["x"]},
        types={},
        module_name="widget",
    )


def _criterion(gherkin: str):
    return criterion_compiler.ParsedCriterion(
        criterion_id="AC-WIDGET-001",
        covers="R-WIDGET-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/widget/acceptance/AC-WIDGET-001.md",
    )


def test_compile_criterion_unresolved_function_is_error_naming_it():
    gherkin = "\n".join(
        [
            "Given a payload is 1",
            'When missing_fn is invoked with {"x": 1}',
            "Then value equals 1",
        ]
    )
    result = criterion_compiler.compile_criterion(_criterion(gherkin), _surface())

    assert _get(result, "status") == "error", result
    message = _get(result, "message")
    assert isinstance(message, str) and message, result
    assert MISSING_FN in message, message
    assert "does not resolve" in message, message
    assert message.startswith("line 2: "), message


def test_compile_criterion_resolved_function_compiles_control():
    gherkin = "\n".join(
        [
            "Given a payload is 1",
            'When known_fn is invoked with {"x": 1}',
            "Then value equals 1",
        ]
    )
    result = criterion_compiler.compile_criterion(_criterion(gherkin), _surface())

    assert _get(result, "status") == "compiled", result
    source = _get(result, "source")
    assert isinstance(source, str) and "known_fn" in source, result


def test_compile_criterion_unresolved_type_is_error_naming_it():
    gherkin = "\n".join(
        [
            "Given a Gadget with size: 1",
            'When known_fn is invoked with {"x": 1}',
            "Then value equals 1",
        ]
    )
    result = criterion_compiler.compile_criterion(_criterion(gherkin), _surface())

    assert _get(result, "status") == "error", result
    message = _get(result, "message")
    assert isinstance(message, str) and message, result
    assert "Gadget" in message, message
    assert "does not resolve" in message, message
    assert message.startswith("line 1: "), message