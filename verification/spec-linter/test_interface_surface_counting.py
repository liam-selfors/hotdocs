"""Regression tests for R-LINT-012's `interface_surface` dimension, as
SPEC_GUIDELINES.md §4 defines it ("How each dimension is measured", D211),
run against this repository's own real `interface/` directories.

Only the public `lint()` is used. A count is visible only once it crosses
the warn threshold (10), so each test copies a real component's
`interface/` into a minimal lint-clean corpus, adds `PAD` extra data
files (one element each), and reads the reported count back. Hand-checked
expected counts are recorded per component.
"""

import re
import shutil
from pathlib import Path

from conftest import REPO_ROOT, spec_linter

PAD = 10

COMPONENT_MD = """---
id: comp-probe
title: Probe
status: draft
owners: [team-a]
sealed: true
source_path: legacy/probe/
depends_on: []
---

# Probe

## Purpose

Probe holds a copied interface.
"""


def _surface(tmp_path: Path, component: str) -> int:
    comp = tmp_path / "specs" / "components" / "probe"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir()
    (tmp_path / "specs" / "glossary.md").write_text("# Glossary\n\n- **Probe** — a test term.\n", encoding="utf-8")
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (comp / "requirements" / "R-PROBE-001.md").write_text(
        "# R-PROBE-001\n\n**R-PROBE-001** — Probe MUST exist.\n", encoding="utf-8")
    (comp / "acceptance" / "AC-PROBE-001.md").write_text(
        "# AC-PROBE-001\n\nCovers: R-PROBE-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a probe\nWhen it runs\nThen it exists\n```\n", encoding="utf-8")
    shutil.copytree(REPO_ROOT / "specs" / "components" / component / "interface", comp / "interface",
                    ignore=shutil.ignore_patterns("guarantees"))
    data = comp / "interface" / "data"
    data.mkdir(exist_ok=True)
    for i in range(PAD):
        (data / f"Pad{i:02d}.md").write_text(f"# `Pad{i:02d}`\n\nPadding.\n", encoding="utf-8")

    report = spec_linter.lint(None, tmp_path)
    findings = report["findings"] if isinstance(report, dict) else report.findings
    for f in findings:
        get = (lambda k: f[k]) if isinstance(f, dict) else (lambda k: getattr(f, k))
        if get("rule_id") == "R-LINT-012" and "probe" in get("file") and "interface_surface" in get("message"):
            return int(re.search(r"interface_surface\D*?(\d+)", get("message")).group(1)) - PAD
    raise AssertionError("no interface_surface finding; the padded count did not cross the threshold")


def test_spec_linter_interface_surface_is_four(tmp_path):
    # 1 CLI invocation + 2 Library functions (lint, load_corpus) + 1 Data file
    # (LintReport; Corpus moved to corpus-loader, D242).
    assert _surface(tmp_path, "spec-linter") == 4


def test_impact_analyzer_interface_surface_is_three(tmp_path):
    # 1 CLI invocation + 1 Library function + 1 Data file (BlastRadiusReport).
    assert _surface(tmp_path, "impact-analyzer") == 3


def test_cache_manager_interface_surface_is_eight(tmp_path):
    # 2 CLI subcommands + 4 Library functions (get, put, now_iso, stats; the
    # `class` lines are not function signatures) + 2 Data files.
    assert _surface(tmp_path, "cache-manager") == 8


def test_criterion_compiler_interface_surface_is_four(tmp_path):
    # 1 CLI invocation wrapped across two lines with a trailing backslash
    # (joined, not double-counted) + 2 Library functions (compile,
    # compile_criterion; GATE_VERSION is not a signature) + 1 Data file.
    assert _surface(tmp_path, "criterion-compiler") == 4
