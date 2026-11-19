# hotdocs-criterion: sha256:25b8f937647c062c2974cff6d330cb76144fc90f0c12e6acbef15a509e684ecf
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _gen_dir():
    return next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
    )


def _tool_root():
    return _gen_dir().parent


def _load_spec_linter():
    base = _gen_dir() / "spec-linter"
    if (base / "spec_linter.py").is_file():
        path = base / "spec_linter.py"
    else:
        path = base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def _assert_lint_clean(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in field(report, "findings")
    ]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(cid, title, source_path, depends_on, assets=None):
    lines = [
        "---",
        "id: " + cid,
        "title: " + title,
        "status: draft",
        "owners: [team-a]",
        "sealed: true",
        "source_path: " + source_path,
        "depends_on: " + depends_on,
    ]
    if assets is not None:
        lines.append("assets: " + assets)
    lines += [
        "---",
        "",
        "# " + title,
        "",
        "## Purpose",
        "",
        "Foo doubles a number.",
        "",
    ]
    return "\n".join(lines)


def _write_component(repo_root, slug, cid, title, req_id, ac_id, source_path,
                     depends_on, assets=None):
    comp = repo_root / "specs" / "components" / slug
    _write(comp / "component.md",
           _component_md(cid, title, source_path, depends_on, assets))
    _write(comp / "requirements" / (req_id + ".md"),
           "# " + req_id + "\n\n**" + req_id + "** \u2014 `foo(x)` MUST return `2 * x`.\n")
    _write(comp / "acceptance" / (ac_id + ".md"),
           "# " + ac_id + "\n"
           "\n"
           "Covers: " + req_id + "\n"
           "Kind: generated-test\n"
           "\n"
           "```gherkin\n"
           "Given x = 2\n"
           "When foo(x) is called\n"
           "Then it returns 4\n"
           "```\n")
    _write(comp / "interface" / "library.md",
           "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    return comp


def _write_glossary(repo_root):
    _write(repo_root / "specs" / "glossary.md",
           "# Glossary\n\n- **Foo** \u2014 a test term.\n")


def _write_app_js_interface(comp):
    _write(comp / "interface" / "assets" / "app.js.md",
           "# app.js\n\n```\nexport function double(x)\n```\n")


def _build_asset_fixture(repo_root):
    _write_glossary(repo_root)
    comp = _write_component(
        repo_root, "foo", "comp-foo", "Foo", "R-FOO-001", "AC-FOO-001",
        "legacy/foo/", "[]", assets="[javascript:static/app.js]",
    )
    _write_app_js_interface(comp)


def _build_nokind_fixture(repo_root):
    _write_glossary(repo_root)
    comp = _write_component(
        repo_root, "foo", "comp-foo", "Foo", "R-FOO-001", "AC-FOO-001",
        "legacy/foo/", "[comp-kind-nokind]", assets="[nokind:static/app.js]",
    )
    _write_app_js_interface(comp)
    _write_component(
        repo_root, "kind-nokind", "comp-kind-nokind", "Kind nokind",
        "R-KJS-001", "AC-KJS-001", "legacy/kind-nokind/", "[]",
    )
    sections = [
        "Layout",
        "Environment",
        "Surface",
        "Running criteria",
        "Strength check",
        "Test author guidance",
        "Generator guidance",
    ]
    text = (
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
    for name in sections:
        text += "## " + name + "\n\n" + name + " text.\n\n"
    _write(repo_root / "specs" / "architecture" / "asset-kind-nokind.md", text)


def test_tool_adapter_guidance_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_asset_fixture(repo_root)
    assert not (repo_root / "gen" / "kind-javascript").exists()

    adapter_path = _tool_root() / "gen" / "kind-javascript" / "kind_javascript.py"
    adapter = load_module(adapter_path, "kind_javascript")
    guide = adapter.guidance()
    G = guide["generator"].strip()
    T = guide["test_author"].strip()

    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    interface = field(bundle, "interface")
    expected_tail = "\n\n## Asset kind: javascript\n\n" + G
    assert interface.endswith(expected_tail), interface

    cbundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(cbundle, "testing") == "\n## Asset kind: javascript\n\n" + T


def test_kind_without_adapter_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_nokind_fixture(repo_root)
    assert not (repo_root / "gen" / "kind-nokind").exists()
    assert not (_tool_root() / "gen" / "kind-nokind").exists()

    _assert_lint_clean(repo_root)

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert type(excinfo.value).__name__ == "PreconditionFailure"
    expected_cls = getattr(spec_bundle_assembler, "PreconditionFailure", None)
    if expected_cls is not None:
        assert isinstance(excinfo.value, expected_cls)
    assert str(excinfo.value) == "unknown asset kind: nokind"