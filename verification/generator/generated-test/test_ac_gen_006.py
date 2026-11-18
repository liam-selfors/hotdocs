# hotdocs-criterion: sha256:f9c20a2699516a37c62e0be01724af54f3fa4fe6cb4a7fc0d655e5ee6dc81591
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import generator


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    path = (
        base / "cache_manager.py"
        if (base / "cache_manager.py").is_file()
        else base / "cache_manager" / "__init__.py"
    )
    return load_module(path, "cache_manager")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _extract_nonce(prompt):
    m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    m = re.search(r"\b([0-9a-f]{32})\b", prompt)
    assert m, "prompt does not state a nonce"
    return m.group(1)


def test_cache_miss_result_written_to_cache_manager(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path
    _build_fixture(repo_root)

    cache_manager = _load_cache_manager()

    model = "claude-sonnet-5"
    spec_bundle_hash = "sha256:" + hashlib.sha256(b"ac-gen-006-bundle").hexdigest()
    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": spec_bundle_hash,
        "spec": "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "hint_code": None,
    }

    fixed_path = "foo.py"
    fixed_content = "def foo(x):\n    return 2 * x\n"

    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted([]), sort_keys=True).encode("utf-8")
    ).hexdigest()
    key = cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )

    # Given an empty cache
    before = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(before, cache_manager.Miss)

    log_path = tmp_path / "mock_calls.log"

    def mock_backend(prompt, model_arg, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = _extract_nonce(prompt)
        text = (
            "-----BEGIN FILE " + nonce + ": " + fixed_path + "-----\n"
            + fixed_content
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model_arg,
            "backend": "mock",
            "model_call_error": None,
        }

    # When generate is called
    result = generator.generate(
        bundle, model, None, repo_root=repo_root, llm_backend=mock_backend
    )

    assert log_path.is_file(), "mock model was never called"
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    files = field(result, "files")
    assert files
    assert files[fixed_path].rstrip("\n") == fixed_content.rstrip("\n")

    # Then cache-manager contains that result under the correct key
    cached = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(cached, cache_manager.Miss), "result was not written to cache"
    assert field(cached, "gate_type") == "generator"
    payload = field(cached, "payload")
    assert field(payload, "component_id") == "comp-foo"
    assert field(payload, "model") == model
    assert field(payload, "prompt_version") == generator.PROMPT_VERSION
    cached_files = field(payload, "files")
    assert dict(cached_files) == dict(files)