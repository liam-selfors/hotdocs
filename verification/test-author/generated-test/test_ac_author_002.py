# hotdocs-criterion: sha256:aea07dab335418745a53d427fba2165a819f0ca756f1e9e0f57583c100d38ced
import dataclasses
import importlib.util
import re
import sys
from pathlib import Path

import test_author


MARKER = "GENONLY_SENTINEL_9b41e2c7"
MARKER_FN = "genonly_hidden_helper_5d03aa"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
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
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write(
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
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    # The sealed component's real code lives at its source_path.
    write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n    return 2 * x\n",
    )
    # Existing gen/<component>/ content, carrying distinctive markers that
    # appear nowhere in the spec corpus.
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "# " + MARKER + "\n"
        "def " + MARKER_FN + "(x):\n"
        "    return x + x\n"
        "\n"
        "def foo(x):\n"
        "    " + repr(MARKER) + "\n"
        "    return " + MARKER_FN + "(x)\n",
    )
    write(
        repo_root / "gen" / "foo" / "NOTES.md",
        "Implementation notes: " + MARKER + "\n",
    )


def tool_gen():
    return next(p for p in Path(test_author.__file__).resolve().parents if p.name == "gen")


def lint_fixture(repo_root):
    gen = next(p for p in Path(test_author.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def load_assembler():
    base = tool_gen() / "spec-bundle-assembler"
    flat = base / "spec_bundle_assembler.py"
    path = flat if flat.is_file() else base / "spec_bundle_assembler" / "__init__.py"
    return load_module(path, "spec_bundle_assembler")


def bundle_items(bundle):
    if dataclasses.is_dataclass(bundle):
        return {f.name: getattr(bundle, f.name) for f in dataclasses.fields(bundle)}
    if isinstance(bundle, dict):
        return dict(bundle)
    return dict(vars(bundle))


def flatten(value):
    if isinstance(value, dict):
        return "\n".join(str(k) + "\n" + flatten(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(flatten(v) for v in value)
    return "" if value is None else str(value)


def test_criterion_bundle_has_no_gen_content(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    build_fixture(repo_root)

    lint_fixture(repo_root)

    assembler = load_assembler()
    bundle = assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    items = bundle_items(bundle)
    assert items, "bundle exposes no fields"
    # The bundle carries the documented spec-derived fields...
    assert field(bundle, "component_id") == "comp-foo"
    assert field(bundle, "criterion_id") == "AC-FOO-001"
    assert "foo(x: int) -> int" in field(bundle, "interface")
    # ...and no field derived from gen/foo/ content.
    assert "hint_code" not in items or not items["hint_code"]
    for name, value in items.items():
        text = flatten(value)
        assert MARKER not in text, "field " + repr(name) + " holds gen/ content"
        assert MARKER_FN not in text, "field " + repr(name) + " holds gen/ content"

    # Inspect what test-author actually sends to the model for that bundle.
    prompt_log = tmp_path / "prompts.log"
    reply_body = "def test_placeholder():\n    assert True"

    def backend(prompt, model, **params):
        with open(prompt_log, "a", encoding="utf-8") as fh:
            fh.write(prompt.replace("\n", "\\n") + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = m.group(1) if m else "0" * 32
        return {
            "text": "-----BEGIN FILE " + nonce + "-----\n" + reply_body + "\n-----END FILE " + nonce + "-----",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle, "claude-sonnet-5", 0, repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") is None

    assert prompt_log.is_file(), "mock backend was never called"
    logged = prompt_log.read_text(encoding="utf-8")
    assert logged.strip(), "mock backend was never called"
    assert MARKER not in logged
    assert MARKER_FN not in logged