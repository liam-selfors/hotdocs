import generator

import importlib.util
import json
import re
import sys
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_gen_dir():
    return next(
        p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
    )


def _load_from_tool(slug):
    module_name = slug.replace("-", "_")
    base = _tool_gen_dir() / slug
    flat = base / f"{module_name}.py"
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
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


def test_ac_gen_016_prompt_instructs_flat_module_or_package_layout(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    _build_corpus(corpus_root)

    spec_linter = _load_from_tool("spec-linter")
    report = spec_linter.lint(None, corpus_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    spec_bundle_assembler = _load_from_tool("spec-bundle-assembler")
    bundle = spec_bundle_assembler.assemble("comp-foo", corpus_root, "cold")
    assert field(bundle, "hint_code") is None

    # A bare repo_root: unsealed, no overrides, so generate reaches the model.
    gen_root = tmp_path / "gen_root"
    gen_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    log_path = tmp_path / "mock_calls.jsonl"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
            f"-----END REPLY {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    generator.generate(
        bundle, "mock-model", repo_root=gen_root, llm_backend=mock_backend
    )

    assert log_path.is_file(), "mock model was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records, "mock model recorded no input"
    prompt = records[0]["prompt"]
    lowered = prompt.lower()

    # Names the real flat module and the real package for comp-foo.
    assert "foo.py" in prompt
    assert "foo/" in prompt
    assert "__init__.py" in prompt
    # Directly under gen/<component>/.
    assert "gen/foo" in prompt
    # Forbids a deeper src/-style layout.
    assert ("src" in lowered) or ("deeper" in lowered) or ("nest" in lowered)