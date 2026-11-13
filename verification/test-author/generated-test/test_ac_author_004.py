import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path

import test_author


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-foo"
CRITERION_ID = "AC-FOO-003"


@dataclass
class _CriterionBundle(Mapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)

    def _names(self):
        return [f.name for f in fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _read_jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


FAKE_CACHE_MANAGER_TEMPLATE = '''import datetime
import json
from dataclasses import dataclass

LOG_PATH = __LOG_PATH__
EXPECTED_MODEL = __EXPECTED_MODEL__
PAYLOAD = json.loads(__PAYLOAD_JSON__)

_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


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


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _log(record):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\\n")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(cache_key, *, repo_root=None):
    gate_version = _field(cache_key, "gate_version")
    model_pin = _field(cache_key, "model_pin")
    _log({
        "op": "get",
        "spec_bundle_hash": _field(cache_key, "spec_bundle_hash"),
        "gate_inputs_hash": _field(cache_key, "gate_inputs_hash"),
        "gate_version": gate_version,
        "model_pin": model_pin,
    })
    if (
        isinstance(gate_version, str)
        and gate_version.startswith("generated_test@")
        and model_pin == EXPECTED_MODEL
    ):
        return CachedResult(
            gate_type="generated_test",
            payload=json.loads(json.dumps(PAYLOAD)),
            stored_at="2026-10-02T00:00:00Z",
        )
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_version = _field(cache_key, "gate_version")
    gate_type = _field(result, "gate_type")
    payload = _field(result, "payload")
    _log({"op": "put", "gate_version": gate_version, "gate_type": gate_type})
    prefix = str(gate_version).split("@", 1)[0]
    if gate_type not in _REQUIRED or prefix != gate_type:
        raise SchemaValidationError("gate_type mismatch: %r vs %r" % (prefix, gate_type))
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    missing = [k for k in _REQUIRED[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("missing payload keys: %r" % (missing,))
    return None


def stats(*, repo_root=None):
    return {"entry_count": 1}


def main(argv=None):
    return 0
'''


def _make_bundle():
    return _CriterionBundle(
        component_id=COMPONENT_ID,
        criterion_id=CRITERION_ID,
        covers="R-FOO-003",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="# R-FOO-003\n\n**R-FOO-003** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
    )


def test_cached_result_returned_and_model_never_called(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    cache_log = logs / "cache_calls.jsonl"
    model_log = logs / "model_calls.jsonl"

    sentinel = "CACHED-SENTINEL-" + uuid.uuid4().hex
    cached_content = (
        "# " + sentinel + "\n"
        "def test_cached_sentinel():\n"
        "    assert True\n"
    )
    cached_path = "verification/foo/generated-test/test_ac_foo_003.py"
    payload = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "model": MODEL,
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": cached_path, "content": cached_content},
        "model_call_error": None,
    }

    fake_src = (
        FAKE_CACHE_MANAGER_TEMPLATE
        .replace("__LOG_PATH__", repr(str(cache_log)))
        .replace("__EXPECTED_MODEL__", repr(MODEL))
        .replace("__PAYLOAD_JSON__", repr(json.dumps(payload)))
    )
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(fake_src, encoding="utf-8")

    def mock_backend(prompt, model, **params):
        with open(model_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        m = re.search(r"BEGIN FILE ([0-9a-fA-F]+)-----", prompt or "")
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_fresh_from_model():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _make_bundle(),
        MODEL,
        0,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert result is not None

    # The mock model must never have been called.
    assert _read_jsonl(model_log) == [], "model backend was called despite a cache hit"

    # The cache must have been consulted with a generated_test@ key for this model.
    cache_records = _read_jsonl(cache_log)
    gets = [r for r in cache_records if r.get("op") == "get"]
    assert gets, "cache-manager.get was never called"
    assert any(
        isinstance(r.get("gate_version"), str)
        and r["gate_version"].startswith("generated_test@")
        and r.get("model_pin") == MODEL
        for r in gets
    ), "no cache lookup used a generated_test@ gate_version with the requested model: %r" % (gets,)

    # The cached result is what is returned.
    assert _get(result, "cache_hit") is True
    assert _get(result, "model_call_error") is None
    assert _get(result, "component_id") == COMPONENT_ID
    assert _get(result, "criterion_id") == CRITERION_ID

    file_obj = _get(result, "file")
    assert file_obj is not None
    content = _get(file_obj, "content")
    assert content == cached_content
    assert sentinel in content
    assert "test_fresh_from_model" not in content