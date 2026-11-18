# hotdocs-criterion: sha256:aea07dab335418745a53d427fba2165a819f0ca756f1e9e0f57583c100d38ced
import dataclasses
import importlib.util
import re
import sys
from pathlib import Path

import test_author


MARKER = "GEN_ONLY_MARKER_7f3a91c2e5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _tool_gen():
    return next(p for p in Path(test_author.__file__).resolve().parents if p.name == "gen")


def _load_tool_module(slug):
    module_name = slug.replace("-", "_")
    base = _tool_gen() / slug
    flat = base / (module_name + ".py")
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    return load_module(path, module_name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "glossary.md",
           "# Glossary\n"
           "\n"
           "- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md",
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
           "Foo doubles a number.\n")
    _write(comp / "requirements" / "R-FOO-001.md",
           "# R-FOO-001\n"
           "\n"
           "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n")
    _write(comp / "acceptance" / "AC-FOO-001.md",
           "# AC-FOO-001\n"
           "\n"
           "Covers: R-FOO-001\n"
           "Kind: generated-test\n"
           "\n"
           "```gherkin\n"
           "Given x = 2\n"
           "When foo(x) is called\n"
           "Then it returns 4\n"
           "```\n")
    _write(comp / "interface" / "library.md",
           "# Library\n"
           "\n"
           "```\n"
           "foo(x: int) -> int\n"
           "```\n")
    _write(comp / "constraints.md",
           "# Constraints\n"
           "\n"
           "None.\n")
    # Sealed component's real code lives under its source_path.
    _write(repo_root / "legacy" / "foo" / "foo.py",
           "def foo(x):\n"
           "    return 2 * x\n")
    # Existing gen/<component>/ content, carrying a unique marker.
    _write(repo_root / "gen" / "foo" / "foo.py",
           "# " + MARKER + " generated source\n"
           "def " + MARKER + "_helper():\n"
           "    return " + repr(MARKER) + "\n"
           "\n"
           "def foo(x):\n"
           "    return 2 * x\n")
    _write(repo_root / "gen" / "foo" / "notes.txt", MARKER + "\n")


def _flatten(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        return "\n".join(str(k) + "\n" + _flatten(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_flatten(v) for v in value)
    return str(value)


def _bundle_field_names(bundle):
    if dataclasses.is_dataclass(bundle):
        return [f.name for f in dataclasses.fields(bundle)]
    return list(bundle.keys())


def test_criterion_bundle_has_no_gen_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    spec_linter = _load_tool_module("spec-linter")
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    assembler = _load_tool_module("spec-bundle-assembler")
    bundle = assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    names = _bundle_field_names(bundle)
    # No field carrying gen/ code (e.g. SpecBundle's hint_code) exists.
    assert "hint_code" not in names
    allowed = {
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary",
        "dependency_interfaces", "module_names",
    }
    assert set(names) <= allowed, names

    for name in names:
        text = _flatten(field(bundle, name))
        assert MARKER not in text, "field " + repr(name) + " carries gen/ content"
        assert "_helper" not in text or MARKER not in text

    # The bundle still carries the interface contract.
    assert "foo(x: int) -> int" in _flatten(field(bundle, "interface"))

    # Passing this bundle to author_test, the prompt the model sees holds no gen/ content.
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = ("-----BEGIN FILE " + nonce + "-----\n"
                "import test_author\n"
                "\n"
                "def test_placeholder():\n"
                "    assert True\n"
                "-----END FILE " + nonce + "-----")
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    out_root = tmp_path / "out"
    out_root.mkdir()
    result = test_author.author_test(
        bundle, "mock-model", 0, repo_root=out_root, llm_backend=backend,
    )
    assert field(result, "model_call_error") is None
    assert prompts, "the mock backend was never called"
    for prompt in prompts:
        assert MARKER not in prompt