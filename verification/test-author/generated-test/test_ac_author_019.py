import re
import sys
from pathlib import Path

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

TEST_FILE_BODY = "def test_placeholder():\n    assert 2 * 2 == 4\n"


class _Bundle:
    """A CriterionBundle stand-in readable both as attributes and as a mapping."""

    def __init__(self, **fields):
        self._fields = dict(fields)
        for k, v in fields.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._fields[key]

    def get(self, key, default=None):
        return self._fields.get(key, default)

    def __contains__(self, key):
        return key in self._fields

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)

    def keys(self):
        return self._fields.keys()

    def items(self):
        return self._fields.items()

    def values(self):
        return self._fields.values()


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


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
        requirement_text="**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_author_test_never_forwards_seed_to_backend(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()

    # Keep llm-endpoint's call log and config discovery, and cache-manager's
    # store, confined to fresh temporary locations.
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    calls = []

    def spy_backend(*args, **kwargs):
        calls.append({"args": args, "kwargs": dict(kwargs)})
        if args:
            prompt = args[0]
        else:
            prompt = kwargs.get("prompt", "")
        if len(args) > 1:
            model = args[1]
        else:
            model = kwargs.get("model")
        match = NONCE_RE.search(prompt or "")
        nonce = match.group(1) if match else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            f"{TEST_FILE_BODY}"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "spy",
            "model_call_error": None,
        }

    model = "claude-sonnet-5"
    non_default_seed = 7

    result = test_author.author_test(
        _make_bundle(),
        model,
        non_default_seed,
        repo_root=repo_root,
        llm_backend=spy_backend,
    )

    # The backend must actually have been reached (fresh repo_root => cache miss).
    assert calls, "spy backend was never called"

    for call in calls:
        args = call["args"]
        kwargs = call["kwargs"]

        # No seed keyword argument at all.
        assert "seed" not in kwargs, f"seed was forwarded to the backend: {kwargs!r}"

        # Only prompt and model reach the backend — nothing else.
        assert len(args) <= 2, f"unexpected extra positional args: {args!r}"
        extra = set(kwargs) - {"prompt", "model"}
        assert not extra, f"unexpected extra keyword args forwarded: {sorted(extra)!r}"

        # Both prompt and model are present (positionally per the contract).
        prompt = args[0] if len(args) >= 1 else kwargs.get("prompt")
        passed_model = args[1] if len(args) >= 2 else kwargs.get("model")
        assert isinstance(prompt, str) and prompt
        assert passed_model is not None
        assert str(passed_model).endswith("claude-sonnet-5")

        # The seed value must not have smuggled itself in positionally either.
        assert non_default_seed not in args[2:]

    # Sanity: the call succeeded end to end with the spy's reply.
    assert _field(result, "model_call_error") is None
    file_value = _field(result, "file")
    assert file_value is not None
    content = _field(file_value, "content")
    assert content is not None and "def test_placeholder" in content