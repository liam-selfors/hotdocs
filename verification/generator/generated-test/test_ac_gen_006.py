"""AC-GEN-006 (covers R-GEN-006).

Given an empty cache and a mock model that returns a fixed result
When generate is called
Then cache-manager contains that result under the correct key afterward
"""

import collections.abc
import dataclasses
import hashlib
import json
import re
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"
MODEL = "claude-sonnet-5"
SPEC_BUNDLE_HASH = "sha256:" + hashlib.sha256(b"ac-gen-006 synthetic bundle").hexdigest()
FIXED_FILES = {"foo.py": "def foo(x):\n    return 2 * x\n"}
EXPECTED_GATE_VERSION = "generator@2.0.0"
EXPECTED_PROMPT_VERSION = "v10"


# ---------------------------------------------------------------------------
# A SpecBundle-shaped value: a dataclass with the documented fields, in the
# documented order, that also reads as a read-only mapping.
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SpecBundle(collections.abc.Mapping):
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

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


GLOSSARY_BODY = "# Glossary\n\n- **Foo** — a test term."


def _make_bundle():
    return SpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary=GLOSSARY_BODY,
        hint_code=None,
    )


# ---------------------------------------------------------------------------
# Fake cache-manager: a file-backed store matching cache-manager's documented
# library contract (get/put/now_iso/stats/main, Miss, SchemaValidationError,
# CacheKey, CachedResult), written in flat-module shape under the fake
# repo_root so the component's dynamic loader picks it up first.
# ---------------------------------------------------------------------------

FAKE_CACHE_MANAGER_SOURCE = '''"""Fake cache_manager for AC-GEN-006: file-backed, records every put/get."""

import dataclasses
import datetime
import json
from pathlib import Path

_STORE_PATH = Path(__STORE_PATH__)
_LOG_PATH = Path(__LOG_PATH__)

_REQUIRED_PAYLOAD_KEYS = {
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
        return hash("Miss")

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


def _plain(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "keys") and hasattr(obj, "__getitem__"):
        try:
            return {str(k): _plain(obj[k]) for k in obj.keys()}
        except Exception:
            pass
    return str(obj)


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key_dict(cache_key):
    return {
        "spec_bundle_hash": _field(cache_key, "spec_bundle_hash"),
        "gate_inputs_hash": _field(cache_key, "gate_inputs_hash"),
        "gate_version": _field(cache_key, "gate_version"),
        "model_pin": _field(cache_key, "model_pin"),
    }


def _load():
    if not _STORE_PATH.is_file():
        return []
    return json.loads(_STORE_PATH.read_text(encoding="utf-8"))


def _save(entries):
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, sort_keys=True), encoding="utf-8")
    tmp.replace(_STORE_PATH)


def _log(record):
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\\n")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(cache_key, *, repo_root=None):
    key = _key_dict(cache_key)
    _log({"op": "get", "key": key})
    try:
        entries = _load()
    except Exception:
        return Miss()
    for entry in reversed(entries):
        if entry["key"] == key:
            r = entry["result"]
            return CachedResult(gate_type=r["gate_type"], payload=r["payload"], stored_at=r["stored_at"])
    return Miss()


def put(cache_key, result, *, repo_root=None):
    key = _key_dict(cache_key)
    gate_version = key["gate_version"] or ""
    key_gate_type = gate_version.split("@", 1)[0]
    gate_type = _field(result, "gate_type")
    payload = _plain(_field(result, "payload"))
    stored_at = _field(result, "stored_at")
    if gate_type not in _REQUIRED_PAYLOAD_KEYS:
        raise SchemaValidationError("unknown gate_type: %r" % (gate_type,))
    if gate_type != key_gate_type:
        raise SchemaValidationError("gate_type %r does not match key gate_version %r" % (gate_type, gate_version))
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    missing = [k for k in _REQUIRED_PAYLOAD_KEYS[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("payload missing required keys: %r" % (missing,))
    entry = {
        "key": key,
        "result": {"gate_type": gate_type, "payload": payload, "stored_at": _plain(stored_at)},
    }
    entries = _load()
    entries = [e for e in entries if e["key"] != key]
    entries.append(entry)
    _save(entries)
    _log({"op": "put", "key": key})
    return None


def stats(*, repo_root=None):
    return {"entry_count": len(_load())}


def main(argv=None):
    return 0
'''


def _write_fake_cache_manager(repo_root, store_path, log_path):
    source = FAKE_CACHE_MANAGER_SOURCE.replace(
        "__STORE_PATH__", repr(str(store_path))
    ).replace("__LOG_PATH__", repr(str(log_path)))
    module_dir = repo_root / "gen" / "cache-manager"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "cache_manager.py").write_text(source, encoding="utf-8")


def _write_fixture_corpus(repo_root):
    specs = repo_root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    comp_dir = specs / "components" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True, exist_ok=True)
    # Not sealed: a sealed target would be refused (R-GEN-009) before any
    # model call, and this criterion needs a successful model call.
    (comp_dir / "component.md").write_text(
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
        "Foo doubles a number.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Mock model backend: llm-endpoint's injectable `backend(prompt, model,
# **params) -> ModelResponse`, always replying with the same fixed files.
# ---------------------------------------------------------------------------

_BEGIN_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})")
_BARE_NONCE_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])")


def _nonces_from_prompt(prompt):
    found = []
    for m in _BEGIN_NONCE_RE.finditer(prompt):
        if m.group(1) not in found:
            found.append(m.group(1))
    if found:
        return found
    for m in _BARE_NONCE_RE.finditer(prompt):
        if m.group(1) not in found:
            found.append(m.group(1))
    return found


def _make_mock_backend(call_log_path):
    def backend(prompt, model, **params):
        nonces = _nonces_from_prompt(prompt)
        with open(call_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model, "nonces": nonces}) + "\n")
        blocks = []
        for nonce in nonces:
            for path, content in FIXED_FILES.items():
                blocks.append(
                    "-----BEGIN FILE %s: %s-----\n%s-----END FILE %s-----"
                    % (nonce, path, content, nonce)
                )
        text = "Here is the implementation.\n\n" + "\n\n".join(blocks) + "\n"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _expected_gate_inputs_hash(retry_feedback):
    encoded = json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _read_jsonl(path):
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize(
    "retry_feedback",
    [None, ["R-FOO-002", "R-FOO-001"]],
    ids=["no-retry-feedback", "with-retry-feedback"],
)
def test_cache_miss_result_is_written_to_cache_under_correct_key(
    tmp_path, monkeypatch, retry_feedback
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    control = tmp_path / "control"
    control.mkdir()
    store_path = control / "cache_store.json"
    cache_log_path = control / "cache_calls.jsonl"
    model_log_path = control / "model_calls.jsonl"

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    _write_fixture_corpus(repo_root)
    _write_fake_cache_manager(repo_root, store_path, cache_log_path)

    # Given an empty cache.
    assert not store_path.exists()

    bundle = _make_bundle()
    backend = _make_mock_backend(model_log_path)

    # When generate is called.
    result = generator.generate(
        bundle,
        MODEL,
        retry_feedback,
        repo_root=repo_root,
        llm_backend=backend,
    )

    # The mock model was actually called, exactly once (a genuine miss).
    model_calls = _read_jsonl(model_log_path)
    assert len(model_calls) == 1, model_calls
    assert model_calls[0]["nonces"], "prompt did not state a nonce for the mock to echo"

    # The fake cache-manager was the one in use.
    cache_calls = _read_jsonl(cache_log_path)
    assert any(c["op"] == "put" for c in cache_calls), cache_calls

    # The returned result is a successful, non-cached generation.
    assert _field(result, "model_call_error") is None
    assert _field(result, "refused") is None
    assert _field(result, "cache_hit") is False
    returned_files = _field(result, "files")
    assert returned_files is not None
    assert dict(returned_files) == FIXED_FILES

    # Then cache-manager contains that result under the correct key.
    expected_key = {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "gate_inputs_hash": _expected_gate_inputs_hash(retry_feedback),
        "gate_version": EXPECTED_GATE_VERSION,
        "model_pin": MODEL,
    }
    assert getattr(generator, "GATE_VERSION", EXPECTED_GATE_VERSION) == EXPECTED_GATE_VERSION

    assert store_path.is_file(), "nothing was written to cache-manager"
    entries = json.loads(store_path.read_text(encoding="utf-8"))
    matching = [e for e in entries if e["key"] == expected_key]
    assert len(matching) == 1, {
        "expected_key": expected_key,
        "stored_keys": [e["key"] for e in entries],
    }

    cached = matching[0]["result"]
    assert cached["gate_type"] == "generator"
    assert isinstance(cached["stored_at"], str) and cached["stored_at"]

    payload = cached["payload"]
    assert isinstance(payload, dict)
    assert payload.get("component_id") == COMPONENT_ID
    assert payload.get("model") == MODEL
    assert payload.get("prompt_version") == EXPECTED_PROMPT_VERSION
    assert dict(payload.get("files") or {}) == FIXED_FILES
    # What was cached is the same result that was returned.
    assert dict(payload.get("files") or {}) == dict(returned_files)