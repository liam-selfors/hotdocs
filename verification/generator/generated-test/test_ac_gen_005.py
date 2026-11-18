# hotdocs-criterion: sha256:a3905129bd7c667b82adee210b40314e5865be86a55eb8fa1d5839832c19f44f
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import generator


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    flat = base / "cache_manager.py"
    path = flat if flat.is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


class Bundle(dict):
    """A SpecBundle-shaped value readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Foo\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def gate_inputs_hash(retry_feedback):
    raw = json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("retry_feedback", [None, ["R-FOO-002", "R-FOO-001"]])
def test_cache_hit_returns_cached_result_without_model_call(tmp_path, monkeypatch, retry_feedback):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "model_calls.log"

    cache_manager = load_cache_manager()
    bundle = make_bundle()
    model = "mock:cached-model"

    key = cache_manager.CacheKey(
        spec_bundle_hash=bundle["spec_bundle_hash"],
        gate_inputs_hash=gate_inputs_hash(retry_feedback),
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )
    cached_files = {"foo.py": "def foo(x):\n    return 2 * x  # CACHED-SENTINEL\n"}
    payload = {
        "component_id": "comp-foo",
        "spec_bundle_hash": bundle["spec_bundle_hash"],
        "model": model,
        "prompt_version": generator.PROMPT_VERSION,
        "cache_hit": False,
        "files": dict(cached_files),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": list(retry_feedback) if retry_feedback is not None else None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type="generator",
            payload=payload,
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=repo_root,
    )
    # Sanity: the cache really holds the entry under this repo_root.
    assert not isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)

    def mock_backend(prompt, model, **params):
        with open(str(log_path), "a", encoding="utf-8") as fh:
            fh.write("called\n")
        import re

        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n    return x + x  # FRESH-FROM-MODEL\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        bundle,
        model,
        retry_feedback,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The mock model is never called.
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == []

    # The cached result is returned.
    assert field(result, "cache_hit") is True
    assert field(result, "files") == cached_files
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "spec_bundle_hash") == bundle["spec_bundle_hash"]