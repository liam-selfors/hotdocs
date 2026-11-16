import json
import re
from pathlib import Path

import pytest

import test_author


CANONICAL_MODEL = "canonical-model-x"


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


class _Bundle:
    """A CriterionBundle stand-in readable both by attribute and as a mapping."""

    _FIELDS = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
    )

    def __init__(self, **kwargs):
        self._data = {}
        for name in self._FIELDS:
            value = kwargs.get(name, {} if name == "dependency_interfaces" else "")
            self._data[name] = value
            setattr(self, name, value)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
    )


def _seed_repo_with_model_a(repo_root: Path, model_a: str) -> None:
    """Lay down this component's 'current code', produced by generator with model_a."""
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text(
        "def foo(x):\n    return 2 * x\n", encoding="utf-8"
    )
    provenance = {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": model_a,
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "def foo(x):\n    return 2 * x\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "model": model_a,
    }
    (gen_dir / ".provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )


def _make_backend(log_path: Path):
    nonce_re = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        match = nonce_re.search(prompt or "")
        nonce = match.group(1) if match else ""
        body = (
            "def test_placeholder():\n"
            "    assert 2 * 2 == 4\n"
        )
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_log(log_path: Path):
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize("model_a", ["anthropic:claude-legacy-a", "ollama:llama3.1:8b"])
def test_author_test_uses_canonical_model_regardless_of_generator_model(
    tmp_path, monkeypatch, model_a
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    _seed_repo_with_model_a(repo_root, model_a)

    log_path = tmp_path / "backend_calls.jsonl"
    backend = _make_backend(log_path)

    result = test_author.author_test(
        _make_bundle(),
        CANONICAL_MODEL,
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )

    calls = _read_log(log_path)
    assert calls, "expected the model backend to be called on a fresh cache"
    for call in calls:
        called_model = call["model"]
        assert called_model == CANONICAL_MODEL or called_model.endswith(":" + CANONICAL_MODEL), (
            f"backend called with {called_model!r}, expected canonical {CANONICAL_MODEL!r}"
        )
        assert model_a not in called_model
        assert model_a.split(":", 1)[-1] not in called_model

    assert _get(result, "model_call_error") is None
    assert _get(result, "model") == CANONICAL_MODEL


def test_author_test_model_is_same_across_different_generator_models(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    observed = []
    for idx, model_a in enumerate(["model-a-first", "model-a-second"]):
        repo_root = tmp_path / f"repo{idx}"
        repo_root.mkdir()
        _seed_repo_with_model_a(repo_root, model_a)

        log_path = tmp_path / f"backend_calls_{idx}.jsonl"
        result = test_author.author_test(
            _make_bundle(),
            CANONICAL_MODEL,
            0,
            repo_root=repo_root,
            llm_backend=_make_backend(log_path),
        )
        calls = _read_log(log_path)
        assert calls, "expected the model backend to be called on a fresh cache"
        models = {c["model"] for c in calls}
        assert all(model_a not in m for m in models)
        observed.append(models)
        assert _get(result, "model") == CANONICAL_MODEL
        assert _get(result, "model_call_error") is None

    assert observed[0] == observed[1]