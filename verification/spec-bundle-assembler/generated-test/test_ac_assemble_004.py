import sys
import tempfile
from pathlib import Path

import spec_bundle_assembler


GLOSSARY_CONTENT = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

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

REQUIREMENT_MD = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

INTERFACE_LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

LEGACY_FOO_PY = "def foo(x):\n    return 2 * x\n"


def _get_field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp_root = specs / "components" / "foo"

    (specs).mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(GLOSSARY_CONTENT)

    (comp_root).mkdir(parents=True, exist_ok=True)
    (comp_root / "component.md").write_text(COMPONENT_MD)

    (comp_root / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_root / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)

    (comp_root / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_root / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)

    (comp_root / "interface").mkdir(parents=True, exist_ok=True)
    (comp_root / "interface" / "library.md").write_text(INTERFACE_LIBRARY_MD)

    (comp_root / "constraints.md").write_text(CONSTRAINTS_MD)

    legacy_foo = repo_root / "legacy" / "foo"
    legacy_foo.mkdir(parents=True, exist_ok=True)
    (legacy_foo / "foo.py").write_text(LEGACY_FOO_PY)


def test_glossary_field_equals_current_glossary_md_content_exactly():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_corpus(repo_root)

        bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

        glossary_field = _get_field(bundle, "glossary")

        assert glossary_field is not None
        assert isinstance(glossary_field, str)
        assert glossary_field == GLOSSARY_CONTENT

        current_glossary_on_disk = (repo_root / "specs" / "glossary.md").read_text()
        assert glossary_field == current_glossary_on_disk


if __name__ == "__main__":
    test_glossary_field_equals_current_glossary_md_content_exactly()
    print("OK")