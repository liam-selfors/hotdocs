import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import spec_bundle_assembler


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )

    _write(
        repo_root
        / "specs"
        / "components"
        / "foo"
        / "requirements"
        / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )

    _write(
        repo_root
        / "specs"
        / "components"
        / "foo"
        / "acceptance"
        / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )

    _write(
        repo_root
        / "specs"
        / "components"
        / "foo"
        / "interface"
        / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
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


_BUNDLE_FIELDS = [
    "component_id",
    "spec_bundle_hash",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
    "hint_code",
]


def _field(bundle, name):
    return bundle.get(name) if isinstance(bundle, dict) else getattr(bundle, name, None)


def _canonical_dict(bundle):
    return {name: _field(bundle, name) for name in _BUNDLE_FIELDS}


def test_assemble_twice_on_unchanged_corpus_is_byte_identical():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_corpus(repo_root)

        spec_linter = _load_spec_linter()
        report = spec_linter.lint(None, repo_root)
        assert report.hard_failures == 0

        bundle1 = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
        bundle2 = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

        dict1 = _canonical_dict(bundle1)
        dict2 = _canonical_dict(bundle2)

        assert dict1 == dict2

        bytes1 = json.dumps(dict1, sort_keys=True).encode("utf-8")
        bytes2 = json.dumps(dict2, sort_keys=True).encode("utf-8")

        assert bytes1 == bytes2