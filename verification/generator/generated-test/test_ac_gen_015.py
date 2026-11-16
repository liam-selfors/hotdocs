import dataclasses
import hashlib
import json
import re
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class _Bundle:
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
    hint_code: dict = None

    def __getitem__(self, key):
        if not isinstance(key, str) or key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
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


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + hashlib.sha256(b"ac-gen-015-bundle").hexdigest(),
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


FAKE_CACHE_MANAGER_TEMPLATE = '''from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

REPO_TAG = {tag!r}
_LOG_PATH = {log_path!r}


def _log(event, **extra):
    record = {{"tag": REPO_TAG, "event": event, "file": __file__}}
    record.update(extra)
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str
    origin_tag: str = REPO_TAG


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


def get(cache_key, *, repo_root=None):
    _log(
        "get",
        is_own_cache_key=isinstance(cache_key, CacheKey),
        repo_root=str(repo_root) if repo_root is not None else None,
    )
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log("put", repo_root=str(repo_root) if repo_root is not None else None)
    return None


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}


_log("loaded")
'''


def _write_fake_cache_manager(repo_root: Path, tag: str, log_path: Path):
    target = repo_root / "gen" / "cache-manager" / "cache_manager.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        FAKE_CACHE_MANAGER_TEMPLATE.format(tag=tag, log_path=str(log_path)),
        encoding="utf-8",
    )


def _mock_backend(prompt, model, **params):
    nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
    text = (
        f"-----BEGIN FILE {nonce}: foo.py-----\n"
        "def foo(x):\n"
        "    return 2 * x\n"
        f"-----END FILE {nonce}-----\n"
        f"-----END REPLY {nonce}-----\n"
    )
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gen_015_per_call_cache_manager_reflects_own_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    log_path = tmp_path / "cache_manager_invocations.jsonl"

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    _write_fake_cache_manager(repo_a, "A", log_path)
    _write_fake_cache_manager(repo_b, "B", log_path)

    bundle = _make_bundle()

    # First call, against repo_a: must not raise (dataclass resolves cleanly).
    result_a = generator.generate(
        bundle, "mock-model", None, repo_root=repo_a, llm_backend=_mock_backend
    )
    entries_after_a = _read_log(log_path)
    a_gets = [e for e in entries_after_a if e["event"] == "get"]

    assert a_gets, "repo_a's cache-manager get was never invoked during the first call"
    assert all(e["tag"] == "A" for e in a_gets), (
        f"first call used a cache-manager not from repo_a: {a_gets}"
    )
    assert all(e["is_own_cache_key"] for e in a_gets), (
        "first call's CacheKey was not repo_a's cache-manager dataclass"
    )
    assert field(result_a, "files"), f"first call produced no files: {result_a!r}"
    assert field(result_a, "model_call_error") is None
    assert field(result_a, "refused") is None

    # Second call, same process, against repo_b: must not raise, and must use repo_b's code.
    result_b = generator.generate(
        bundle, "mock-model", None, repo_root=repo_b, llm_backend=_mock_backend
    )
    entries_after_b = _read_log(log_path)
    new_entries = entries_after_b[len(entries_after_a):]
    b_gets = [e for e in new_entries if e["event"] == "get"]

    assert b_gets, (
        "repo_b's cache-manager get was never invoked during the second call "
        f"(new log entries: {new_entries})"
    )
    assert all(e["tag"] == "B" for e in b_gets), (
        f"second call reused another repo_root's cache-manager: {b_gets}"
    )
    assert not any(e["tag"] == "A" for e in new_entries), (
        f"repo_a's cache-manager was exercised during the second call: {new_entries}"
    )
    assert all(e["is_own_cache_key"] for e in b_gets), (
        "second call's CacheKey was not repo_b's cache-manager dataclass"
    )
    assert field(result_b, "files"), f"second call produced no files: {result_b!r}"
    assert field(result_b, "model_call_error") is None
    assert field(result_b, "refused") is None