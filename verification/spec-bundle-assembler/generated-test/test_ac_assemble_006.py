import spec_bundle_assembler

import importlib.util
import json
import sys
from pathlib import Path

import pytest


BUNDLE_FIELDS = [
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, title: str, depends_on: str, purpose: str,
                     rid: str, acid: str, req_text: str, signature: str) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        f"depends_on: {depends_on}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n",
    )
    _write(
        comp_dir / "requirements" / f"{rid}.md",
        f"# {rid}\n"
        "\n"
        f"**{rid}** — {req_text}\n",
    )
    _write(
        comp_dir / "acceptance" / f"{acid}.md",
        f"# {acid}\n"
        "\n"
        f"Covers: {rid}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When the function is called with x\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        f"{signature}\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    _write_component(
        root, "foo", "Foo", "[]", "Foo doubles a number.",
        "R-FOO-001", "AC-FOO-001",
        "`foo(x)` MUST return `2 * x`.",
        "foo(x: int) -> int",
    )
    _write_component(
        root, "bar", "Bar", "[comp-foo]", "Bar doubles a number using Foo.",
        "R-BAR-001", "AC-BAR-001",
        "`bar(x)` MUST return `foo(x)`.",
        "bar(x: int) -> int",
    )

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0
    return root


def _serialize(bundle) -> bytes:
    data = {name: field(bundle, name) for name in BUNDLE_FIELDS}
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("component_id", ["comp-foo", "comp-bar"])
def test_assemble_twice_is_byte_identical(repo_root, component_id):
    first = spec_bundle_assembler.assemble(component_id, repo_root)
    second = spec_bundle_assembler.assemble(component_id, repo_root)

    assert field(first, "component_id") == component_id
    assert field(second, "component_id") == component_id

    for name in BUNDLE_FIELDS:
        assert field(first, name) == field(second, name), name

    assert _serialize(first) == _serialize(second)
    assert field(first, "spec_bundle_hash") == field(second, "spec_bundle_hash")


def test_assemble_cli_json_twice_is_byte_identical(repo_root, capsys):
    argv = ["comp-bar", "--format=json", f"--repo-root={repo_root}"]

    code1 = spec_bundle_assembler.main(list(argv))
    out1 = capsys.readouterr().out
    code2 = spec_bundle_assembler.main(list(argv))
    out2 = capsys.readouterr().out

    assert code1 == 0
    assert code2 == 0
    assert out1.encode("utf-8") == out2.encode("utf-8")
    parsed = json.loads(out1)
    assert parsed["component_id"] == "comp-bar"