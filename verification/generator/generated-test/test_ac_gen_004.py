# hotdocs-criterion: sha256:9461041486b91ab9a0d85d1990794a3348688bd2810709141b243d486bf291fb
import json
import re
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
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
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
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


def _bundle():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** \u2014 a test term.",
        "hint_code": None,
    }


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        nonce = m.group(1) if m else ""
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_model_identifier_passed_through_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "model_calls.log"
    backend = _make_backend(log_path)

    model_a = "anthropic:test-model-alpha-ac-gen-004"
    model_b = "ollama:test-model-beta-ac-gen-004"
    bundle = _bundle()

    result_a = generator.generate(bundle, model_a, repo_root=repo_root, llm_backend=backend)
    result_b = generator.generate(bundle, model_b, repo_root=repo_root, llm_backend=backend)

    for result in (result_a, result_b):
        assert field(result, "refused") is None
        assert field(result, "model_call_error") is None
        assert field(result, "cache_hit") is False

    assert log_path.exists(), "mock model was never called"
    recorded = [
        json.loads(line)["model"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert recorded == [model_a, model_b]

    assert field(result_a, "model") == model_a
    assert field(result_b, "model") == model_b