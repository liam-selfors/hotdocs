import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"
SPEC_BUNDLE_HASH = "sha256:" + hashlib.sha256(b"ac-gen-005-fixture-bundle").hexdigest()
MODEL = "anthropic:claude-sonnet-5"
CACHED_FILES = {"foo.py": "def foo(x):\n    return 2 * x  # served-from-cache-marker\n"}


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


@dataclasses.dataclass
class FakeSpecBundle:
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
        if key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __contains__(self, key):
        return key in self.keys()


def _gate_inputs_hash(retry_feedback):
    payload = json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


FAKE_CACHE_MANAGER_TEMPLATE = '''
import dataclasses
import json
import datetime

_LOG_PATH = {log_path!r}
_EXPECTED_KEY = json.loads({expected_key_json!r})
_CACHED_PAYLOAD = json.loads({payload_json!r})
_STORED_AT = "2026-10-02T00:00:00Z"

_REQUIRED = {{
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}}


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


def _f(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key_dict(cache_key):
    return {{
        "spec_bundle_hash": _f(cache_key, "spec_bundle_hash"),
        "gate_inputs_hash": _f(cache_key, "gate_inputs_hash"),
        "gate_version": _f(cache_key, "gate_version"),
        "model_pin": _f(cache_key, "model_pin"),
    }}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\\n")


def get(cache_key, *, repo_root=None):
    key = _key_dict(cache_key)
    hit = key == _EXPECTED_KEY
    _log({{"op": "get", "key": key, "hit": hit}})
    if hit:
        return CachedResult(gate_type="generator", payload=dict(_CACHED_PAYLOAD), stored_at=_STORED_AT)
    return Miss()


def put(cache_key, result, *, repo_root=None):
    key = _key_dict(cache_key)
    gate_version = key.get("gate_version") or ""
    expected_type = gate_version.split("@", 1)[0]
    gate_type = _f(result, "gate_type")
    payload = _f(result, "payload") or {{}}
    _log({{"op": "put", "key": key, "gate_type": gate_type}})
    if gate_type != expected_type or gate_type not in _REQUIRED:
        raise SchemaValidationError("gate_type mismatch")
    missing = [k for k in _REQUIRED[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("missing payload keys: %s" % missing)
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 1}}


def main(argv=None):
    print(json.dumps({{"entry_count": 1}}))
    return 0
'''


COMPONENT_MD = (
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
    "Foo doubles a number.\n"
)


def _build_repo(tmp_path, retry_feedback):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "components" / COMPONENT_SLUG / "requirements").mkdir(parents=True)
    (repo_root / "specs" / "components" / COMPONENT_SLUG / "acceptance").mkdir(parents=True)
    (repo_root / "specs" / "components" / COMPONENT_SLUG / "interface").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    (repo_root / "specs" / "components" / COMPONENT_SLUG / "component.md").write_text(
        COMPONENT_MD, encoding="utf-8"
    )

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cache_log = log_dir / "cache_calls.jsonl"
    model_log = log_dir / "model_calls.jsonl"

    expected_key = {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "gate_inputs_hash": _gate_inputs_hash(retry_feedback),
        "gate_version": generator.GATE_VERSION,
        "model_pin": MODEL,
    }
    cached_payload = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model": MODEL,
        "prompt_version": generator.PROMPT_VERSION,
        "cache_hit": False,
        "files": dict(CACHED_FILES),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": list(retry_feedback) if retry_feedback is not None else None,
    }

    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_TEMPLATE.format(
            log_path=str(cache_log),
            expected_key_json=json.dumps(expected_key, sort_keys=True),
            payload_json=json.dumps(cached_payload, sort_keys=True),
        ),
        encoding="utf-8",
    )
    return repo_root, cache_log, model_log, expected_key


def _read_log(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize(
    "retry_feedback",
    [None, ["R-FOO-003", "R-FOO-001"]],
    ids=["blind", "with-retry-feedback"],
)
def test_cache_hit_returns_cached_result_without_model_call(tmp_path, monkeypatch, retry_feedback):
    repo_root, cache_log, model_log, expected_key = _build_repo(tmp_path, retry_feedback)
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    model_log_path = str(model_log)

    def mock_backend(prompt, model, **params):
        with open(model_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        return {
            "text": "no file blocks here",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = FakeSpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
    )

    retry_arg = list(retry_feedback) if retry_feedback is not None else None
    result = generator.generate(
        bundle,
        MODEL,
        retry_arg,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The mock model must never have been called.
    model_calls = _read_log(model_log)
    assert model_calls == [], f"mock model was called on a cache hit: {model_calls}"

    # The cache must have been consulted with exactly the documented key.
    cache_calls = _read_log(cache_log)
    gets = [c for c in cache_calls if c.get("op") == "get"]
    assert gets, "cache-manager.get was never called"
    assert any(c.get("key") == expected_key for c in gets), (
        f"no cache get used the documented key {expected_key}; got {[c.get('key') for c in gets]}"
    )

    # The cached result is what was returned.
    assert result is not None
    assert _field(result, "cache_hit") is True
    files = _field(result, "files")
    assert dict(files or {}) == CACHED_FILES
    assert _field(result, "model_call_error") is None
    assert _field(result, "refused") is None
    assert _field(result, "component_id") == COMPONENT_ID
    assert _field(result, "spec_bundle_hash") == SPEC_BUNDLE_HASH
    assert _field(result, "model") == MODEL
    assert _field(result, "prompt_version") == generator.PROMPT_VERSION