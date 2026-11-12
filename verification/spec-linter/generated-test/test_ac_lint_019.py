import os
import tempfile
import unittest
from pathlib import Path

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [alice]
sealed: true
source_path: legacy/widget
---

# Widget

## Purpose

Widget does a small, self-contained thing for testing purposes.

## Scope

- In scope: the widget behavior.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

REQUIREMENT_MD = """# R-WIDGET-001

**R-WIDGET-001** — The widget MUST return the same output for the same input.
This matches existing behavior; do not regenerate.
"""

ACCEPTANCE_MD = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: compiled

```gherkin
Given a widget input
When the widget runs twice
Then both outputs are equal
```
"""

CONSTRAINTS_MD = """# Constraints

- None beyond existing behavior.
"""

GLOSSARY_MD = """# Glossary

- **Widget** — a test-only fixture component.
"""

REQ_REL = "specs/components/widget/requirements/R-WIDGET-001.md"
COMP_REL = "specs/components/widget/component.md"


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _build_corpus(root):
    _write(root, COMP_REL, COMPONENT_MD)
    _write(root, REQ_REL, REQUIREMENT_MD)
    _write(root, "specs/components/widget/acceptance/AC-WIDGET-001.md", ACCEPTANCE_MD)
    _write(root, "specs/components/widget/constraints.md", CONSTRAINTS_MD)
    _write(root, "specs/glossary.md", GLOSSARY_MD)


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def _lint019(report):
    findings = _get(report, "findings", None) or []
    return [f for f in findings if _get(f, "rule_id") == "R-LINT-019"]


def _add_trailing_spaces(root, rel, line_index):
    """Append two spaces to the given 0-based line; return its 1-based number."""
    path = Path(root) / rel
    lines = path.read_text(encoding="utf-8").split("\n")
    assert lines[line_index].strip() != "", "target line must be non-empty"
    assert not lines[line_index].endswith((" ", "\t"))
    lines[line_index] = lines[line_index] + "  "
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return line_index + 1


class TestACLINT019TrailingWhitespace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name).resolve()
        _build_corpus(self.repo_root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_corpus_has_no_trailing_whitespace_findings(self):
        report = spec_linter.lint(None, self.repo_root)
        self.assertEqual(_lint019(report), [])

    def test_two_trailing_spaces_in_requirement_reports_fail_on_that_line(self):
        # Sanity baseline: no R-LINT-019 findings before the defect is introduced.
        baseline = spec_linter.lint(None, self.repo_root)
        self.assertEqual(_lint019(baseline), [])
        baseline_hard = _get(baseline, "hard_failures", 0) or 0

        # Line index 2 is the requirement body's first sentence line.
        line_no = _add_trailing_spaces(self.repo_root, REQ_REL, 2)
        self.assertEqual(line_no, 3)

        report = spec_linter.lint(None, self.repo_root)
        findings = _lint019(report)
        self.assertTrue(findings, "expected an R-LINT-019 finding")

        for f in findings:
            self.assertEqual(_get(f, "severity"), "fail")

        locations = {(_norm(_get(f, "file")), _get(f, "line")) for f in findings}
        self.assertEqual(len(locations), 1, f"unexpected locations: {locations}")
        (file_value, line_value) = next(iter(locations))
        self.assertTrue(
            file_value.endswith(REQ_REL),
            f"finding file {file_value!r} does not name {REQ_REL!r}",
        )
        self.assertFalse(os.path.isabs(file_value), "file must be relative to repo_root")
        self.assertEqual(line_value, line_no)

        hard = _get(report, "hard_failures", 0) or 0
        self.assertGreaterEqual(hard, 1)
        self.assertGreater(hard, baseline_hard - 1)
        self.assertGreaterEqual(hard, baseline_hard + 1)

    def test_fail_not_warn_even_without_strict(self):
        line_no = _add_trailing_spaces(self.repo_root, REQ_REL, 2)
        report = spec_linter.lint(None, self.repo_root, strict=False)
        findings = _lint019(report)
        self.assertTrue(findings)
        self.assertTrue(all(_get(f, "severity") == "fail" for f in findings))
        self.assertTrue(all(_get(f, "line") == line_no for f in findings))

    def test_trailing_spaces_in_frontmatter_line_reported(self):
        # Line index 2 of component.md is "title: Widget", inside the frontmatter.
        line_no = _add_trailing_spaces(self.repo_root, COMP_REL, 2)
        self.assertEqual(line_no, 3)
        report = spec_linter.lint(None, self.repo_root)
        findings = _lint019(report)
        self.assertTrue(findings, "expected an R-LINT-019 finding for a frontmatter line")
        matching = [
            f for f in findings
            if _norm(_get(f, "file")).endswith(COMP_REL) and _get(f, "line") == line_no
        ]
        self.assertTrue(matching, f"no finding names {COMP_REL}:{line_no}: {findings}")
        for f in matching:
            self.assertEqual(_get(f, "severity"), "fail")

    def test_report_to_json_contains_finding(self):
        line_no = _add_trailing_spaces(self.repo_root, REQ_REL, 2)
        report = spec_linter.lint(None, self.repo_root)
        to_json = getattr(report, "to_json", None)
        if to_json is None:
            self.skipTest("report has no to_json")
        data = to_json()
        if isinstance(data, str):
            import json
            data = json.loads(data)
        findings = [f for f in data["findings"] if f.get("rule_id") == "R-LINT-019"]
        self.assertTrue(findings)
        self.assertTrue(all(f["severity"] == "fail" for f in findings))
        self.assertTrue(any(
            _norm(f["file"]).endswith(REQ_REL) and f["line"] == line_no for f in findings
        ))
        self.assertGreaterEqual(data["summary"]["hard_failures"], 1)


if __name__ == "__main__":
    unittest.main()