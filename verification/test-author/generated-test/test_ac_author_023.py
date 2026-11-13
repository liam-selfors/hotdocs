import json
import re
from pathlib import Path

import pytest

import test_author


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
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))
        if self.dependency_interfaces is None:
            self.dependency_interfaces = {}

    def __getitem__(self, key):
        if key in self._FIELDS:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def __contains__(self, key):
        return key in self._FIELDS

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_backend(log_path: Path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = re.search(r"BEGIN FILE ([0-9a-fA-F]{32})", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _bundles():
    interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
    glossary = "# Glossary\n\n- **Foo** — a test term."
    return [
        _Bundle(
            component_id="comp-foo",
            criterion_id="AC-FOO-001",
            covers="R-FOO-001",
            criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
            requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
            interface=interface,
            glossary=glossary,
            dependency_interfaces={},
        ),
        _Bundle(
            component_id="comp-bar",
            criterion_id="AC-BAR-007",
            covers="R-BAR-007",
            criterion_text="Given an empty list\nWhen bar(xs) is called\nThen it returns 0",
            requirement_text="# R-BAR-007\n\n**R-BAR-007** — `bar(xs)` MUST return the length of `xs`.",
            interface="# Library\n\n```\nbar(xs: list) -> int\n```",
            glossary=glossary,
            dependency_interfaces={"comp-foo": interface},
        ),
    ]


def _assert_truncation_instruction(prompt: str):
    lower = prompt.lower()

    # The prompt must name the precision mismatch it guards against.
    assert "microsecond" in lower, "prompt never mentions microsecond-precision bounds"

    # Some instruction must tell the author to truncate before/after to the
    # field's documented precision, all in one nearby passage.
    found = False
    for m in re.finditer(r"truncat", lower):
        start = max(0, m.start() - 700)
        window = lower[start : m.end() + 700]
        if (
            "before" in window
            and "after" in window
            and "precision" in window
        ):
            found = True
            break
    assert found, (
        "prompt has no instruction to truncate before/after window bounds "
        "to the field's documented precision"
    )

    # It concerns a wall-clock write-time window check.
    assert any(
        k in lower
        for k in ("wall-clock", "wall clock", "write time", "write-time", "timestamp")
    ), "prompt's truncation instruction is not tied to a write-time/timestamp check"


def test_prompt_instructs_truncating_write_time_window_bounds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "backend_calls.jsonl"
    backend = _make_backend(log_path)

    bundles = _bundles()
    # The bundle content itself carries nothing about timestamps or
    # truncation, so any such instruction must come from the prompt itself.
    for b in bundles:
        blob = " ".join(
            str(b.get(k)) for k in _Bundle._FIELDS
        ).lower()
        for word in ("truncat", "microsecond", "precision", "wall-clock"):
            assert word not in blob

    for i, bundle in enumerate(bundles):
        repo_root = tmp_path / f"repo_{i}"
        repo_root.mkdir()
        result = test_author.author_test(
            bundle,
            "claude-sonnet-5",
            seed=0,
            repo_root=repo_root,
            llm_backend=backend,
        )
        assert _field(result, "model_call_error") is None

    assert log_path.is_file(), "the mock backend was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) >= len(bundles)

    for rec in records:
        prompt = rec["prompt"]
        assert isinstance(prompt, str) and prompt
        _assert_truncation_instruction(prompt)