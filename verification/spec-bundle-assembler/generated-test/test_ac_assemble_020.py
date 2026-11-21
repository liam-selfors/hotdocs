# hotdocs-criterion: sha256:2075a775502f80910fe63f20695d5a214b37316decff8d34fde57451d96c542c
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _gen_dir():
    return next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )


def _lint_clean(repo_root):
    gen = _gen_dir()
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec_linter = load_module(path, "spec_linter")
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in report.findings
        if field(f, "severity") == "fail"
    ]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug, comp_id, title, req_id, ac_id, source_path,
               depends_on, assets_line):
    root = repo_root / "specs" / "components" / slug
    text = (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: " + source_path + "\n"
        "depends_on: " + depends_on + "\n"
    )
    if assets_line is not None:
        text += assets_line + "\n"
    text += (
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n"
    )
    _write(root / "component.md", text)
    _write(
        root / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        root / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        root / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(root / "constraints.md", "# Constraints\n\nNone.\n")
    return root


def _glossary(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )


def _asset_interface(foo_root):
    _write(
        foo_root / "interface" / "assets" / "app.js.md",
        "# app.js\n\n```\nexport function double(x)\n```\n",
    )


def test_tool_adapter_guidance_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _glossary(repo_root)
    foo_root = _component(
        repo_root, "foo", "comp-foo", "Foo", "R-FOO-001", "AC-FOO-001",
        "legacy/foo/", "[]", "assets: [javascript:static/app.js]",
    )
    _asset_interface(foo_root)
    assert not (repo_root / "gen" / "kind-javascript").exists()

    _lint_clean(repo_root)

    gen = _gen_dir()
    tool_root = gen.parent
    adapter_path = tool_root / "gen" / "kind-javascript" / "kind_javascript.py"
    adapter = load_module(adapter_path, "kind_javascript")
    guide = adapter.guidance()
    G = guide["generator"].strip()
    T = guide["test_author"].strip()

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    interface = field(bundle, "interface")
    assert interface.endswith("\n\n## Asset kind: javascript\n\n" + G)

    cbundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    assert field(cbundle, "testing") == "\n## Asset kind: javascript\n\n" + T


def test_kind_without_adapter_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _glossary(repo_root)
    foo_root = _component(
        repo_root, "foo", "comp-foo", "Foo", "R-FOO-001", "AC-FOO-001",
        "legacy/foo/", "[comp-kind-nokind]", "assets: [nokind:static/app.js]",
    )
    _asset_interface(foo_root)
    _component(
        repo_root, "kind-nokind", "comp-kind-nokind", "Kind nokind",
        "R-KJS-001", "AC-KJS-001", "legacy/kind-nokind/", "[]", None,
    )
    definition = (
        "---\n"
        "id: kind-nokind\n"
        "title: Asset kind nokind\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Asset kind nokind\n"
        "\n"
    )
    for name in ["Layout", "Environment", "Surface", "Running criteria",
                 "Strength check", "Test author guidance", "Generator guidance"]:
        definition += "## " + name + "\n\n" + name + " text.\n\n"
    _write(repo_root / "specs" / "architecture" / "asset-kind-nokind.md",
           definition)
    assert not (repo_root / "gen" / "kind-nokind").exists()
    assert not (_gen_dir() / "kind-nokind").exists()

    _lint_clean(repo_root)

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble("comp-foo", repo_root)
    exc = excinfo.value
    assert type(exc).__name__ == "PreconditionFailure"
    expected_cls = getattr(spec_bundle_assembler, "PreconditionFailure", None)
    if expected_cls is not None:
        assert isinstance(exc, expected_cls)
    assert str(exc) == "unknown asset kind: nokind"