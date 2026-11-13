import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


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

GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

REQUIREMENT_MD = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _field_names(bundle):
    if isinstance(bundle, dict):
        return list(bundle.keys())
    if dataclasses.is_dataclass(bundle):
        return [f.name for f in dataclasses.fields(bundle)]
    keys = getattr(bundle, "keys", None)
    if callable(keys):
        return list(keys())
    return [n for n in vars(bundle).keys() if not n.startswith("_")]


def _flatten_strings(value):
    out = []
    if value is None:
        return out
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            out.append(str(k))
            out.extend(_flatten_strings(v))
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            out.extend(_flatten_strings(v))
    else:
        out.append(str(value))
    return out


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    return root


def test_cold_bundle_includes_spec_interface_constraints_and_excludes_acceptance(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report.get("hard_failures") if isinstance(report, dict) else getattr(report, "hard_failures", None)
    assert hard == 0, f"fixture is not lint-clean: {report}"

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    assert bundle is not None

    assert _get(bundle, "component_id") == "comp-foo"

    spec_text = _get(bundle, "spec")
    assert isinstance(spec_text, str)
    assert "Foo doubles a number." in spec_text
    assert "R-FOO-001" in spec_text
    assert "MUST return" in spec_text

    interface_text = _get(bundle, "interface")
    assert isinstance(interface_text, str)
    assert "foo(x: int) -> int" in interface_text

    constraints_text = _get(bundle, "constraints")
    assert isinstance(constraints_text, str)
    assert "None." in constraints_text

    assert _get(bundle, "hint_code") is None

    names = _field_names(bundle)
    assert names, "bundle exposes no fields"
    for name in names:
        assert "acceptance" not in name.lower(), f"bundle has acceptance-derived field {name!r}"
        assert "criteri" not in name.lower(), f"bundle has criterion-derived field {name!r}"

    acceptance_markers = ["AC-FOO-001", "Given x = 2", "Then it returns 4", "Kind: generated-test", "Covers: R-FOO-001"]
    for name in names:
        for text in _flatten_strings(_get(bundle, name)):
            for marker in acceptance_markers:
                assert marker not in text, (
                    f"field {name!r} contains acceptance/ content {marker!r}"
                )