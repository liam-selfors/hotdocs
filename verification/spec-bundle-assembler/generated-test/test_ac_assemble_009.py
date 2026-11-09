import tempfile
import shutil
import unittest
from pathlib import Path

import spec_bundle_assembler


def get_field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def has_field(obj, name):
    if isinstance(obj, dict):
        return name in obj
    return hasattr(obj, name)


GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""

REQ_001_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`. REQ001_MARKER_TEXT_UNIQUE
"""

REQ_002_MD = """# R-FOO-002

**R-FOO-002** — `foo(x)` MUST also be idempotent on repeated calls. REQ002_MARKER_TEXT_UNIQUE
"""

AC_001_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4, CRITERION001_MARKER_UNIQUE
```
"""

AC_002_MD = """# AC-FOO-002

Covers: R-FOO-002
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called twice
Then both calls return 4, CRITERION002_MARKER_UNIQUE
```
"""

INTERFACE_LIBRARY_MD = """# Library

```
foo(x: int) -> int
```

INTERFACE_MARKER_UNIQUE
"""

CONSTRAINTS_MD = """# Constraints

None. CONSTRAINTS_MARKER_SHOULD_NOT_APPEAR
"""

GEN_FOO_PY = """GEN_MARKER_SHOULD_NOT_APPEAR = True
"""


class TestAcAssemble009(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo_root = Path(self.tmp)

        specs = self.repo_root / "specs"
        specs.mkdir(parents=True)
        (specs / "glossary.md").write_text(GLOSSARY_MD)

        comp_dir = specs / "components" / "foo"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(COMPONENT_MD)

        req_dir = comp_dir / "requirements"
        req_dir.mkdir()
        (req_dir / "R-FOO-001.md").write_text(REQ_001_MD)
        (req_dir / "R-FOO-002.md").write_text(REQ_002_MD)

        acc_dir = comp_dir / "acceptance"
        acc_dir.mkdir()
        (acc_dir / "AC-FOO-001.md").write_text(AC_001_MD)
        (acc_dir / "AC-FOO-002.md").write_text(AC_002_MD)

        iface_dir = comp_dir / "interface"
        iface_dir.mkdir()
        (iface_dir / "library.md").write_text(INTERFACE_LIBRARY_MD)

        (comp_dir / "constraints.md").write_text(CONSTRAINTS_MD)

        gen_dir = self.repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True)
        (gen_dir / "foo.py").write_text(GEN_FOO_PY)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_criterion_bundle_contains_only_its_own_scoped_content(self):
        bundle = spec_bundle_assembler.assemble_criterion(
            "comp-foo", "AC-FOO-001", self.repo_root
        )

        self.assertEqual(get_field(bundle, "component_id"), "comp-foo")
        self.assertEqual(get_field(bundle, "criterion_id"), "AC-FOO-001")
        self.assertEqual(get_field(bundle, "covers"), "R-FOO-001")

        criterion_text = get_field(bundle, "criterion_text")
        requirement_text = get_field(bundle, "requirement_text")
        interface_text = get_field(bundle, "interface")
        glossary_text = get_field(bundle, "glossary")

        self.assertIsNotNone(criterion_text)
        self.assertIsNotNone(requirement_text)
        self.assertIsNotNone(interface_text)
        self.assertIsNotNone(glossary_text)

        self.assertIn("CRITERION001_MARKER_UNIQUE", criterion_text)
        self.assertIn("REQ001_MARKER_TEXT_UNIQUE", requirement_text)
        self.assertIn("INTERFACE_MARKER_UNIQUE", interface_text)
        self.assertIn("a test term", glossary_text)

        forbidden_markers = [
            "GEN_MARKER_SHOULD_NOT_APPEAR",
            "CONSTRAINTS_MARKER_SHOULD_NOT_APPEAR",
            "REQ002_MARKER_TEXT_UNIQUE",
            "CRITERION002_MARKER_UNIQUE",
        ]
        fields_to_check = [
            criterion_text,
            requirement_text,
            interface_text,
            glossary_text,
        ]
        for field_value in fields_to_check:
            for marker in forbidden_markers:
                self.assertNotIn(marker, field_value)

        self.assertFalse(has_field(bundle, "hint_code"))

        dependency_interfaces = get_field(bundle, "dependency_interfaces")
        self.assertEqual(dependency_interfaces, {})


if __name__ == "__main__":
    unittest.main()