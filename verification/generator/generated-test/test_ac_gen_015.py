"""AC-GEN-015 (covers R-GEN-014).

Given two different repo_root values, each with its own
gen/cache-manager/cache_manager.py defining a real dataclass (with string
annotations, so dataclasses' internals must resolve
sys.modules[cls.__module__] during class-body evaluation), calling
generator.generate twice in the same process -- once per repo_root -- must:

  * never raise (each cache-manager's dataclasses resolve cleanly), and
  * have each call served by its OWN repo_root's cache-manager code, not the
    other call's (no stale reuse of the first-loaded module).

Which fake ran is confirmed via invocation records each fake appends to a
log FILE whose path the test constructs, never via sys.modules lookups.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import generator


MODEL = "anthropic:claude-sonnet-5"


# Template for a fake cache_manager module. Placeholders are substituted
# with repr() values; no dedent is applied to interpolated text.
FAKE_CACHE_MANAGER_TEMPLATE = '''from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MARKER = __MARKER__
_LOG_PATH = __LOG_PATH__

_KNOWN_GATE_TYPES = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}

_STORE = {}


def _log(op, **extra):
    record = {"marker": MARKER, "op": op, "module_name": __name__, "file": __file__}
    record.update(extra)
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\\n")


def _read(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
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


def _key_tuple(cache_key):
    return (
        _read(cache_key, "spec_bundle_hash"),
        _read(cache_key, "gate_inputs_hash"),
        _read(cache_key, "gate_version"),
        _read(cache_key, "model_pin"),
    )


def get(cache_key, *, repo_root=None):
    try:
        _log(
            "get",
            spec_bundle_hash=_read(cache_key, "spec_bundle_hash"),
            gate_version=_read(cache_key, "gate_version"),
            repo_root=str(repo_root) if repo_root is not None else None,
        )
        hit = _STORE.get(_key_tuple(cache_key))
        if hit is None:
            return Miss()
        return hit
    except Exception:
        return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_version = _read(cache_key, "gate_version") or ""
    expected_type = gate_version.split("@", 1)[0]
    gate_type = _read(result, "gate_type")
    payload = _read(result, "payload")
    if expected_type not in _KNOWN_GATE_TYPES or gate_type != expected_type:
        raise SchemaValidationError("gate_type mismatch: %r vs %r" % (gate_type, expected_type))
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    missing = [k for k in _KNOWN_GATE_TYPES[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("payload missing keys: %r" % (missing,))
    _log(
        "put",
        spec_bundle_hash=_read(cache_key, "spec_bundle_hash"),
        gate_version=gate_version,
        repo_root=str(repo_root) if repo_root is not None else None,
    )
    _STORE[_key_tuple(cache_key)] = result
    return None


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stats(*, repo_root=None):
    return {"entry_count": len(_STORE)}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("inspect", "stats"):
        return 2
    if argv[0] == "stats":
        print(json.dumps(stats()))
        return 0
    print(json.dumps({"result": "miss"}))
    return 0


_log("load", cache_key_fields=list(CacheKey.__dataclass_fields__), cached_result_fields=list(CachedResult.__dataclass_fields__))
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

GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""


@dataclass
class FakeSpecBundle(Mapping):
    """A SpecBundle-shaped value: documented fields, in order, readable as a mapping."""

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

    _FIELDS = (
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    )

    def __getitem__(self, key):
        if key in self._FIELDS:
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    __hash__ = None


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_bundle(spec_bundle_hash):
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash=spec_bundle_hash,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def _build_repo(repo_root, marker, log_path):
    (repo_root / "specs" / "components" / "foo").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "component.md").write_text(
        COMPONENT_MD, encoding="utf-8"
    )
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD, encoding="utf-8")

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    source = FAKE_CACHE_MANAGER_TEMPLATE.replace("__MARKER__", repr(marker)).replace(
        "__LOG_PATH__", repr(str(log_path))
    )
    (cm_dir / "cache_manager.py").write_text(source, encoding="utf-8")


def _read_log(log_path):
    if not log_path.is_file():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _call_records(records):
    return [r for r in records if r.get("op") in ("get", "put")]


def _mock_backend(prompt, model, **params):
    match = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
    if match is None:
        match = re.search(r"\b([0-9a-f]{32})\b", prompt)
    assert match is not None, "prompt did not state a 32-hex-digit nonce"
    nonce = match.group(1)
    text = (
        "Here is the implementation.\n"
        "-----BEGIN FILE " + nonce + ": foo.py-----\n"
        "def foo(x):\n"
        "    return 2 * x\n"
        "-----END FILE " + nonce + "-----\n"
    )
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def _assert_successful_result(result, bundle):
    files = _field(result, "files")
    assert _field(result, "model_call_error") is None, _field(result, "model_call_error")
    assert _field(result, "refused") is None, _field(result, "refused")
    assert files, "expected non-empty files"
    assert _field(result, "spec_bundle_hash") == bundle.spec_bundle_hash
    assert _field(result, "component_id") == "comp-foo"


def _is_under(path_str, root):
    try:
        Path(path_str).resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def test_ac_gen_015_per_call_cache_manager_resolves_from_each_repo_root(tmp_path, monkeypatch):
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    logs = tmp_path / "logs"
    logs.mkdir()
    log_a = logs / "cache_manager_a.jsonl"
    log_b = logs / "cache_manager_b.jsonl"

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    _build_repo(repo_a, "A", log_a)
    _build_repo(repo_b, "B", log_b)

    hash_a = "sha256:" + "a" * 64
    hash_b = "sha256:" + "b" * 64
    bundle_a = _make_bundle(hash_a)
    bundle_b = _make_bundle(hash_b)

    # First call: repo A. Must not raise (A's dataclasses resolve cleanly).
    result_a = generator.generate(bundle_a, MODEL, None, repo_root=repo_a, llm_backend=_mock_backend)
    _assert_successful_result(result_a, bundle_a)

    records_a_after_first = _read_log(log_a)
    assert any(r.get("op") == "load" for r in records_a_after_first), (
        "repo A's cache-manager was never loaded"
    )
    calls_a_first = _call_records(records_a_after_first)
    assert calls_a_first, "repo A's cache-manager get/put was never invoked"
    for r in records_a_after_first:
        assert r.get("marker") == "A"
        assert _is_under(r.get("file"), repo_a), r
    for r in calls_a_first:
        assert r.get("spec_bundle_hash") == hash_a, r
    load_a = [r for r in records_a_after_first if r.get("op") == "load"][0]
    assert load_a.get("cache_key_fields") == [
        "spec_bundle_hash",
        "gate_inputs_hash",
        "gate_version",
        "model_pin",
    ]

    assert _call_records(_read_log(log_b)) == [], "repo B's fake ran during repo A's call"

    # Second call, same process: repo B. Must not raise, and must use B's code.
    result_b = generator.generate(bundle_b, MODEL, None, repo_root=repo_b, llm_backend=_mock_backend)
    _assert_successful_result(result_b, bundle_b)

    records_b = _read_log(log_b)
    assert any(r.get("op") == "load" for r in records_b), (
        "repo B's cache-manager was never loaded; the first call's module was reused"
    )
    calls_b = _call_records(records_b)
    assert calls_b, "repo B's cache-manager get/put was never invoked; stale module reused"
    for r in records_b:
        assert r.get("marker") == "B"
        assert _is_under(r.get("file"), repo_b), r
    for r in calls_b:
        assert r.get("spec_bundle_hash") == hash_b, r
    load_b = [r for r in records_b if r.get("op") == "load"][0]
    assert load_b.get("cache_key_fields") == [
        "spec_bundle_hash",
        "gate_inputs_hash",
        "gate_version",
        "model_pin",
    ]

    # Repo A's module must not have served the second call.
    calls_a_after_second = _call_records(_read_log(log_a))
    assert len(calls_a_after_second) == len(calls_a_first), (
        "repo A's cache-manager was invoked during repo B's call (stale module reuse)"
    )
    assert all(r.get("spec_bundle_hash") != hash_b for r in calls_a_after_second)