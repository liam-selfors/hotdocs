import pathlib
import sys

import pytest

import spec_completeness_assistant


_MISSING = object()


def _get(obj, key, default=_MISSING):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _public_names(obj):
    if isinstance(obj, dict):
        return set(obj.keys())
    return {name for name in dir(obj) if not name.startswith("_")}


BLOCKING_NAMES = {
    "block",
    "blocks",
    "blocking",
    "blocks_merge",
    "merge_block",
    "fail",
    "fails",
    "failed",
    "should_fail",
    "should_block",
    "is_blocking",
    "abort",
    "gate",
    "gated",
    "check_readiness",
    "exit",
    "sys_exit",
    "raise_error",
    "raise_for_status",
}


GLOSSARY_TEXT = """# Glossary

No corpus-specific terms are needed for this fixture.
"""

COMPONENT_MD = """---
id: comp-foo
title: Foo Component
status: draft
owners: [lselfors@gmail.com]
sealed: true
source_path: /fake/src/foo.py
depends_on: []
---

# Foo Component

## Purpose

A fixture component used only to exercise
comp-spec-completeness-assistant's assist() function. It does not
depend on comp-spec-completeness-assistant.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — Foo MUST do the fixture thing.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001

```gherkin
Given foo
When foo runs
Then foo does the fixture thing
```
"""


SPEC_LINTER_SRC = '''
def lint(paths, repo_root, strict=False, judge=None):
    with open(LOG_PATH_TOKEN, "a", encoding="utf-8") as fh:
        fh.write("lint-called")
    return {
        "findings": [],
        "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0},
    }
'''

IMPACT_ANALYZER_SRC = '''
def compute_blast_radius(changed_ids, repo_root):
    with open(LOG_PATH_TOKEN, "a", encoding="utf-8") as fh:
        fh.write("impact-called")
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None},
        ],
        "precondition_error": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER_SRC = '''
def assemble(component_id, repo_root, mode="cold"):
    with open(LOG_PATH_TOKEN, "a", encoding="utf-8") as fh:
        fh.write("assemble-called:" + str(mode))
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fake",
        "spec": "fake spec text",
        "interface": "fake interface text",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary text",
        "hint_code": {"foo.py": "# fake code"} if mode == "hint" else None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    with open(LOG_PATH_TOKEN, "a", encoding="utf-8") as fh:
        fh.write("assemble_criterion-called")
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FAKE-001",
        "criterion_text": "fake criterion text",
        "requirement_text": "fake requirement text",
        "interface": "fake interface text",
        "glossary": "fake glossary text",
    }
'''


def _write_fake_dependency(path, source_template, log_path):
    source = source_template.replace("LOG_PATH_TOKEN", repr(str(log_path)))
    path.write_text(source, encoding="utf-8")


def test_assist_returns_report_without_raising_or_gating(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    components_dir = repo_root / "specs" / "components" / "foo"
    requirements_dir = components_dir / "requirements"
    acceptance_dir = components_dir / "acceptance"
    requirements_dir.mkdir(parents=True, exist_ok=True)
    acceptance_dir.mkdir(parents=True, exist_ok=True)

    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_TEXT, encoding="utf-8")
    (components_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (requirements_dir / "R-FOO-001.md").write_text(REQUIREMENT_MD, encoding="utf-8")
    (acceptance_dir / "AC-FOO-001.md").write_text(ACCEPTANCE_MD, encoding="utf-8")

    gen_linter_dir = repo_root / "gen" / "spec-linter"
    gen_impact_dir = repo_root / "gen" / "impact-analyzer"
    gen_assembler_dir = repo_root / "gen" / "spec-bundle-assembler"
    for d in (gen_linter_dir, gen_impact_dir, gen_assembler_dir):
        d.mkdir(parents=True, exist_ok=True)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_linter = logs_dir / "spec_linter.log"
    log_impact = logs_dir / "impact_analyzer.log"
    log_assembler = logs_dir / "spec_bundle_assembler.log"

    _write_fake_dependency(gen_linter_dir / "spec_linter.py", SPEC_LINTER_SRC, log_linter)
    _write_fake_dependency(
        gen_impact_dir / "impact_analyzer.py", IMPACT_ANALYZER_SRC, log_impact
    )
    _write_fake_dependency(
        gen_assembler_dir / "spec_bundle_assembler.py",
        SPEC_BUNDLE_ASSEMBLER_SRC,
        log_assembler,
    )

    def _no_exit(code=0):
        raise AssertionError(
            "assist() invoked sys.exit(%r); it must never exit anything" % (code,)
        )

    monkeypatch.setattr(sys, "exit", _no_exit)

    changed_ids = ["comp-foo"]

    try:
        report = spec_completeness_assistant.assist(changed_ids, pathlib.Path(repo_root))
    except BaseException as exc:
        pytest.fail("assist() raised unexpectedly: %r" % (exc,))

    assert report is not None

    for field in (
        "lint_findings",
        "predicted_blast_radius",
        "hint_previews",
        "completeness_score",
        "completeness_rationale",
        "redundancy_flags",
        "degraded",
    ):
        assert _get(report, field) is not _MISSING, (
            "CompletenessReport is missing field %r" % (field,)
        )

    assert _get(report, "degraded") is True

    assert not _get(report, "completeness_score")
    assert not _get(report, "completeness_rationale")
    assert not _get(report, "redundancy_flags")

    assert _get(report, "lint_findings") == []

    blast_radius = _get(report, "predicted_blast_radius")
    assert "comp-foo" in blast_radius

    hint_previews = _get(report, "hint_previews")
    assert _get(hint_previews, "comp-foo", _MISSING) is not _MISSING

    report_names = _public_names(report)
    offending = report_names & BLOCKING_NAMES
    assert not offending, (
        "CompletenessReport exposes field/method(s) that could gate or "
        "block something: %r" % (offending,)
    )

    assert log_linter.exists() and log_linter.read_text(encoding="utf-8") != ""
    assert log_impact.exists() and log_impact.read_text(encoding="utf-8") != ""
    assert log_assembler.exists() and log_assembler.read_text(encoding="utf-8") != ""