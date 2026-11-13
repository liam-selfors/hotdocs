import dataclasses
import json
import urllib.error
from pathlib import Path

import pytest

import generator


ENDPOINT_CATEGORIES = {"network", "auth", "rate_limit", "timeout"}


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


@dataclasses.dataclass
class _FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.keys():
            return getattr(self, key)
        return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return key in self.keys()

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self):
        return [getattr(self, k) for k in self.keys()]


FAKE_CACHE_MANAGER_TEMPLATE = '''
import dataclasses
import json
from datetime import datetime, timezone

_LOG_PATH = {log_path!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\\n")


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    pass


def _key_dict(cache_key):
    if isinstance(cache_key, dict):
        return dict(cache_key)
    try:
        return dataclasses.asdict(cache_key)
    except Exception:
        return {{"repr": repr(cache_key)}}


def get(cache_key, *, repo_root=None):
    _log({{"op": "get", "key": _key_dict(cache_key)}})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log({{"op": "put", "key": _key_dict(cache_key)}})
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}


def main(argv=None):
    print(json.dumps({{"result": "miss"}}))
    return 0
'''


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


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "specs").mkdir()
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    cache_log = tmp_path / "cache_calls.jsonl"
    cache_log.write_text("", encoding="utf-8")
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_TEMPLATE.format(log_path=str(cache_log)),
        encoding="utf-8",
    )
    return repo_root, cache_log


def _bundle():
    return _FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="None.",
        glossary="- **Foo** — a test term.",
        hint_code=None,
    )


def _read_cache_log(cache_log):
    records = []
    for line in cache_log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _gen_files_written(repo_root):
    target = repo_root / "gen" / "foo"
    if not target.exists():
        return []
    return [p for p in target.rglob("*") if p.is_file()]


def _local_cache_files(repo_root):
    cache_dir = repo_root / ".hotdocs" / "cache"
    if not cache_dir.exists():
        return []
    return [p for p in cache_dir.rglob("*") if p.is_file()]


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root, cache_log = _build_repo(tmp_path)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root, cache_log


def test_network_error_yields_model_call_error_no_files_no_cache_hit(env):
    repo_root, cache_log = env
    calls = []

    def failing_backend(prompt, model, **params):
        calls.append({"prompt": prompt, "model": model})
        raise urllib.error.URLError("connection refused")

    result = generator.generate(
        _bundle(),
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=failing_backend,
    )

    assert calls, "the mock model was never called"

    error = _field(result, "model_call_error")
    assert error is not None and error, f"expected model_call_error, got {error!r}"
    category = _field(error, "category")
    assert category in ENDPOINT_CATEGORIES, f"unexpected category {category!r}"

    files = _field(result, "files")
    assert not files, f"expected empty files, got {files!r}"

    assert _field(result, "cache_hit") is False
    assert _field(result, "refused") is None

    puts = [r for r in _read_cache_log(cache_log) if r.get("op") == "put"]
    assert puts == [], f"a failed call must not be cached: {puts!r}"
    assert _gen_files_written(repo_root) == []
    assert _local_cache_files(repo_root) == []


def test_response_without_file_blocks_is_empty_response(env):
    repo_root, cache_log = env
    calls = []

    def blockless_backend(prompt, model, **params):
        calls.append({"prompt": prompt, "model": model})
        return {
            "text": "I considered the spec carefully but produced no files here.\n"
            "def foo(x):\n    return 2 * x\n",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        _bundle(),
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=blockless_backend,
    )

    assert calls, "the mock model was never called"

    error = _field(result, "model_call_error")
    assert error is not None and error, f"expected model_call_error, got {error!r}"
    assert _field(error, "category") == "empty_response"
    assert isinstance(_field(error, "message"), str)

    files = _field(result, "files")
    assert not files, f"expected empty files, got {files!r}"

    assert _field(result, "cache_hit") is False
    assert _field(result, "refused") is None

    puts = [r for r in _read_cache_log(cache_log) if r.get("op") == "put"]
    assert puts == [], f"an empty response must not be cached: {puts!r}"
    assert _gen_files_written(repo_root) == [], "nothing may be written to gen/foo/"
    assert _local_cache_files(repo_root) == []