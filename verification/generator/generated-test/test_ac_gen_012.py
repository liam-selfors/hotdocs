import json
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path

import pytest

import generator


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


@dataclass
class _FakeSpecBundle(Mapping):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def _names(self):
        return [f.name for f in fields(self)]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: false
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
        encoding="utf-8",
    )
    (comp_dir / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp_dir / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    return repo_root


def _make_bundle() -> _FakeSpecBundle:
    return _FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a1" * 32,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
    )


def test_hanging_model_yields_single_attempt_model_call_error(tmp_path, monkeypatch):
    # Isolate cache-manager to the local fallback store and llm-endpoint's call log
    # to a scratch working directory.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    repo_root = _make_repo(tmp_path)
    bundle = _make_bundle()

    log_path = tmp_path / "mock_model_calls.log"
    log_path.write_text("", encoding="utf-8")

    def hanging_backend(prompt, model, **params):
        # Record the attempt to a file the test controls.
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model, "t": time.time()}) + "\n")
        # The model never responds; what eventually surfaces is the SDK's own
        # default timeout firing, simulated here as the timeout exception the
        # bounded call raises once it gives up waiting.
        time.sleep(0.2)
        raise TimeoutError("model did not respond before the default timeout")

    outcome = {}

    def run():
        try:
            outcome["result"] = generator.generate(
                bundle,
                "anthropic:claude-sonnet-5",
                None,
                repo_root=repo_root,
                llm_backend=hanging_backend,
            )
        except BaseException as exc:  # pragma: no cover - surfaced below
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=120)

    assert not worker.is_alive(), "generate() hung instead of completing with model_call_error"
    assert "error" not in outcome, f"generate() raised instead of returning: {outcome.get('error')!r}"

    result = outcome["result"]

    model_call_error = _get(result, "model_call_error")
    assert model_call_error, "expected model_call_error to be set for a hanging model"

    assert not _get(result, "files"), "a failed call must not produce files"
    assert _get(result, "refused") is None, "a hanging model call is not a refusal"
    assert _get(result, "cache_hit") is False, "a failed call is never a cache hit"

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"expected exactly one model call attempt (no internal retry), got {len(lines)}"
    )