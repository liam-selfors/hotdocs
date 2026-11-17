import dataclasses
import importlib.util
import re
import sys
from pathlib import Path

import test_author


SENTINEL = "GEN_ONLY_SENTINEL_7f3a9c51d2"
GEN_SOURCE = (
    "# " + SENTINEL + " module docstring marker\n"
    "def foo(x):\n"
    "    marker = " + repr(SENTINEL + "_BODY") + "\n"
    "    return x + x\n"
)

ALLOWED_FIELDS = {
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
    "module_names",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _tool_gen():
    return next(
        p for p in Path(test_author.__file__).resolve().parents if p.name == "gen"
    )


def _load_tool_module(slug):
    module_name = slug.replace("-", "_")
    base = _tool_gen() / slug
    flat = base / (module_name + ".py")
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    return load_module(path, module_name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
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
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
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
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    # Real code for the sealed component lives under its source_path.
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")
    # Existing gen/<component>/ content carrying a unique sentinel.
    _write(repo_root / "gen" / "foo" / "foo.py", GEN_SOURCE)
    _write(repo_root / "gen" / "foo" / "NOTES.txt", SENTINEL + "_NOTES\n")


def _bundle_items(bundle):
    if isinstance(bundle, dict):
        return dict(bundle)
    if dataclasses.is_dataclass(bundle):
        return {f.name: getattr(bundle, f.name) for f in dataclasses.fields(bundle)}
    return {k: getattr(bundle, k) for k in vars(bundle)}


def _flatten(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(str(k) + "\n" + _flatten(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_flatten(v) for v in value)
    return str(value)


def test_criterion_bundle_contains_nothing_from_gen_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    spec_linter = _load_tool_module("spec-linter")
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    assembler = _load_tool_module("spec-bundle-assembler")
    bundle = assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    # Inspect the bundle: only the documented, spec-derived fields, and no
    # value carries anything from gen/foo/.
    items = _bundle_items(bundle)
    assert set(items) <= ALLOWED_FIELDS, set(items) - ALLOWED_FIELDS
    assert "hint_code" not in items
    for name, value in items.items():
        text = _flatten(value)
        assert SENTINEL not in text, "field " + repr(name) + " holds gen/ content"
        assert "return x + x" not in text, "field " + repr(name) + " holds gen/ code"

    # The bundle test_author actually consumes, and the prompt it builds from
    # it with a repo_root holding gen/foo/, likewise carry no gen/ content.
    log_path = tmp_path / "prompts.log"
    body_text = "import foo\n\n\ndef test_placeholder():\n    assert True\n"

    def backend(prompt, model, **params):
        with open(log_path, "a") as fh:
            fh.write(prompt)
            fh.write("\n=====END PROMPT=====\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = m.group(1) if m else "0" * 32
        return {
            "text": "-----BEGIN FILE " + nonce + "-----\n"
            + body_text
            + "\n-----END FILE " + nonce + "-----",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle, "claude-sonnet-5", 0, repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") is None

    assert log_path.is_file(), "mock backend was never called"
    prompts = log_path.read_text()
    assert prompts.strip() != ""
    assert SENTINEL not in prompts
    assert "return x + x" not in prompts