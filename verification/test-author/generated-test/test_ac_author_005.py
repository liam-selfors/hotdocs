import json
import re
from pathlib import Path

import test_author


FIXED_TEST_CODE = (
    "def test_fixed_result():\n"
    "    assert 2 * 2 == 4\n"
)

MODEL = "claude-sonnet-5"


FAKE_CACHE_MANAGER = '''
import dataclasses
import datetime
import json
from pathlib import Path

_STORE_PATH = Path(__STORE_PATH__)
_LOG_PATH = Path(__LOG_PATH__)

_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


class SchemaValidationError(ValueError):
    pass


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0

    def __repr__(self):
        return "Miss()"


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


def _as_dict(obj):
    if isinstance(obj, dict):
        return dict(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    try:
        return dict(vars(obj))
    except TypeError:
        return {"value": obj}


def _key_dict(cache_key):
    d = _as_dict(cache_key)
    return {
        "spec_bundle_hash": d.get("spec_bundle_hash"),
        "gate_inputs_hash": d.get("gate_inputs_hash"),
        "gate_version": d.get("gate_version"),
        "model_pin": d.get("model_pin"),
    }


def _key_str(cache_key):
    return json.dumps(_key_dict(cache_key), sort_keys=True, default=str)


def _load_store():
    if not _STORE_PATH.is_file():
        return {}
    try:
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\\n")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(cache_key, *, repo_root=None):
    _log({"op": "get", "key": _key_dict(cache_key)})
    store = _load_store()
    entry = store.get(_key_str(cache_key))
    if entry is None:
        return Miss()
    return CachedResult(
        gate_type=entry.get("gate_type"),
        payload=entry.get("payload"),
        stored_at=entry.get("stored_at"),
    )


def put(cache_key, result, *, repo_root=None):
    key = _key_dict(cache_key)
    res = _as_dict(result)
    gate_version = key.get("gate_version") or ""
    gate_type = gate_version.split("@", 1)[0]
    if res.get("gate_type") != gate_type:
        raise SchemaValidationError("gate_type mismatch")
    if gate_type not in _REQUIRED:
        raise SchemaValidationError("unknown gate type")
    payload = res.get("payload")
    payload_d = _as_dict(payload) if payload is not None else {}
    missing = [k for k in _REQUIRED[gate_type] if k not in payload_d]
    if missing:
        raise SchemaValidationError("missing payload keys: %r" % (missing,))
    entry = {
        "gate_type": res.get("gate_type"),
        "payload": json.loads(json.dumps(payload_d, default=lambda o: _as_dict(o))),
        "stored_at": res.get("stored_at"),
    }
    store = _load_store()
    store[_key_str(cache_key)] = entry
    _STORE_PATH.write_text(json.dumps(store, sort_keys=True, default=str), encoding="utf-8")
    _log({"op": "put", "key": key, "result": entry})
    return None


def stats(*, repo_root=None):
    return {"entry_count": len(_load_store())}


def main(argv=None):
    return 0
'''


class _Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _read_log(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cache_miss_result_written_under_looked_up_key(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    store_path = tmp_path / "fake_cache_store.json"
    cache_log = tmp_path / "fake_cache_log.jsonl"
    backend_log = tmp_path / "backend_log.jsonl"

    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    fake_src = (
        FAKE_CACHE_MANAGER
        .replace("__STORE_PATH__", repr(str(store_path)))
        .replace("__LOG_PATH__", repr(str(cache_log)))
    )
    (fake_dir / "cache_manager.py").write_text(fake_src, encoding="utf-8")

    # Empty cache precondition.
    assert not store_path.exists()

    def mock_backend(prompt, model, **params):
        with open(backend_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", prompt)
        assert m is not None, "nonce not found in prompt"
        nonce = m.group(1)
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            f"{FIXED_TEST_CODE}"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _make_bundle(), MODEL, 0, repo_root=repo_root, llm_backend=mock_backend
    )

    # The fresh call happened and succeeded.
    assert len(_read_log(backend_log)) == 1
    assert _field(result, "model_call_error") is None
    assert _field(result, "cache_hit") is False
    result_file = _field(result, "file")
    assert result_file is not None
    result_content = _field(result_file, "content")
    assert isinstance(result_content, str)
    assert result_content.strip() == FIXED_TEST_CODE.strip()

    records = _read_log(cache_log)
    gets = [r for r in records if r["op"] == "get"]
    puts = [r for r in records if r["op"] == "put"]

    # A lookup (miss) happened, and exactly one write followed it.
    assert gets, "author_test never looked up the cache"
    assert len(puts) == 1, f"expected exactly one put, got {len(puts)}"
    first_get_index = records.index(gets[0])
    put_index = records.index(puts[0])
    assert first_get_index < put_index

    put_record = puts[0]
    key = put_record["key"]

    # Written under the very key that was looked up on the miss.
    assert key == gets[0]["key"]
    assert isinstance(key.get("gate_version"), str)
    assert key["gate_version"].startswith("generated_test@")
    assert key.get("model_pin") == MODEL
    assert key.get("spec_bundle_hash")
    assert key.get("gate_inputs_hash")

    # The stored result is the model's result.
    stored = put_record["result"]
    assert stored["gate_type"] == "generated_test"
    payload = stored["payload"]
    assert payload.get("component_id") == "comp-foo"
    assert payload.get("criterion_id") == "AC-FOO-001"
    assert payload.get("model") == MODEL
    stored_file = payload.get("file")
    assert stored_file is not None
    stored_content = stored_file.get("content") if isinstance(stored_file, dict) else stored_file
    assert isinstance(stored_content, str)
    assert stored_content.strip() == FIXED_TEST_CODE.strip()
    assert stored_content == result_content

    # And the cache actually holds it afterward under that key.
    store = json.loads(store_path.read_text(encoding="utf-8"))
    key_str = json.dumps(
        {
            "spec_bundle_hash": key.get("spec_bundle_hash"),
            "gate_inputs_hash": key.get("gate_inputs_hash"),
            "gate_version": key.get("gate_version"),
            "model_pin": key.get("model_pin"),
        },
        sort_keys=True,
    )
    assert key_str in store
    assert store[key_str]["payload"]["file"] == stored_file