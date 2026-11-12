import re
import shutil
import tempfile
import unittest
from pathlib import Path

import size_checker


_VOCAB = (
    "this component validates widget records against a declared schema and "
    "reports every structural problem it finds back to the calling tool so "
    "that authors can correct their inputs before any later stage consumes "
    "them while keeping the reporting format stable predictable and easy to "
    "read for both humans and automated consumers alike across every run"
).split()


def _purpose_words(n):
    words = [_VOCAB[i % len(_VOCAB)] for i in range(n)]
    for w in words:
        assert not re.match(r"^D\d+", w)
    lines = []
    for i in range(0, n, 12):
        lines.append(" ".join(words[i:i + 12]))
    return "\n".join(lines)


def _field(finding, name):
    if isinstance(finding, dict):
        return finding.get(name)
    return getattr(finding, name, None)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root, purpose_word_count):
    specs = root / "specs"
    for sub in ("product", "architecture", "vars", "decisions"):
        (specs / sub).mkdir(parents=True, exist_ok=True)
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing that is checked.\n",
    )
    comp = specs / "components" / "widget"
    purpose = _purpose_words(purpose_word_count)
    component_md = (
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widget validation.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )
    _write(comp / "component.md", component_md)
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget checker MUST report "
        "invalid records.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\nKind: generated-test\n\n"
        "Given an invalid record\nWhen checked\nThen it is reported\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n- None beyond the defaults.\n",
    )
    return "specs/components/widget/component.md"


def _purpose_findings(findings, rel):
    out = []
    for f in findings:
        if _field(f, "rule_id") != "R-SIZE-004":
            continue
        file_val = _field(f, "file")
        if file_val is None:
            continue
        if str(file_val).replace("\\", "/") == rel:
            out.append(f)
    return out


class TestAcSize004(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, n):
        rel = _build_repo(self.tmp, n)
        findings = size_checker.check(self.tmp)
        self.assertIsInstance(findings, list)
        return _purpose_findings(findings, rel)

    def test_160_word_purpose_without_citation_fails(self):
        found = self._run(160)
        fails = [f for f in found if _field(f, "severity") == "fail"]
        self.assertTrue(
            fails,
            f"expected an R-SIZE-004 fail finding for a 160-word Purpose, got {found!r}",
        )
        f = fails[0]
        self.assertIn("150", str(_field(f, "message")))
        line = _field(f, "line")
        self.assertIsInstance(line, int)
        self.assertNotIsInstance(line, bool)
        self.assertGreaterEqual(line, 1)
        if isinstance(f, dict):
            self.assertEqual(
                set(f.keys()), {"rule_id", "severity", "file", "line", "message"}
            )

    def test_151_word_purpose_fails(self):
        found = self._run(151)
        fails = [f for f in found if _field(f, "severity") == "fail"]
        self.assertTrue(fails, f"151 words is above 150; got {found!r}")
        self.assertIn("150", str(_field(fails[0], "message")))

    def test_150_word_purpose_warns_not_fails(self):
        found = self._run(150)
        fails = [f for f in found if _field(f, "severity") == "fail"]
        warns = [f for f in found if _field(f, "severity") == "warn"]
        self.assertEqual(fails, [], f"150 words is not above 150; got {found!r}")
        self.assertTrue(warns, f"150 words is above 80; expected warn, got {found!r}")

    def test_100_word_purpose_warns_not_fails(self):
        found = self._run(100)
        fails = [f for f in found if _field(f, "severity") == "fail"]
        warns = [f for f in found if _field(f, "severity") == "warn"]
        self.assertEqual(fails, [])
        self.assertTrue(warns, f"100 words is above 80; expected warn, got {found!r}")

    def test_80_word_purpose_has_no_finding(self):
        found = self._run(80)
        self.assertEqual(found, [], f"80 words is within the cap; got {found!r}")


if __name__ == "__main__":
    unittest.main()