# hotdocs-criterion: sha256:6ddb106927f57598d46ecd461ec8b0147aafdc1e954b6f0eafdc802e3b0382c0
import json
import urllib.request
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "class CacheKey:\n"
    "    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None, gate_version=None, model_pin=None):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_inputs_hash = gate_inputs_hash\n"
    "        self.gate_version = gate_version\n"
    "        self.model_pin = model_pin\n"
    "\n"
    "\n"
    "class CachedResult:\n"
    "    def __init__(self, gate_type=None, payload=None, stored_at=None):\n"
    "        self.gate_type = gate_type\n"
    "        self.payload = payload\n"
    "        self.stored_at = stored_at\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    import datetime\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime(" + repr("%Y-%m-%dT%H:%M:%SZ") + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {" + repr("entry_count") + ": 0}\n"
)


def make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "foo.py").write_text(
        "def add_numbers(alpha, beta):\n"
        "    total = alpha + beta\n"
        "    result = total * 2 + 1\n"
        "    return result\n",
        encoding="utf-8",
    )
    return repo_root


VALID_ENTRY = {
    "reference_id": "ref-001",
    "license_family": "GPL",
    "risk_tier": "high",
    "hashes": ["0" * 64],
}


def _corpus(**overrides):
    base = {"corpus_version": 1, "block_threshold": 0.7, "entries": [dict(VALID_ENTRY)]}
    base.update(overrides)
    return json.dumps(base)


INVALID_CORPORA = {
    "not-json": "{this is not json",
    "json-list": json.dumps([dict(VALID_ENTRY)]),
    "no-entries": json.dumps({"corpus_version": 1, "block_threshold": 0.7}),
    "corpus-version-x": _corpus(corpus_version="x"),
    "block-threshold-0": _corpus(block_threshold=0),
    "block-threshold-1.5": _corpus(block_threshold=1.5),
    "hashes-not-list": _corpus(entries=[dict(VALID_ENTRY, hashes="abc")]),
    "risk-tier-severe": _corpus(entries=[dict(VALID_ENTRY, risk_tier="severe")]),
}


def test_missing_corpus_is_unreadable_and_blocks(tmp_path, monkeypatch):
    repo_root = make_repo(tmp_path)
    missing = repo_root / "does-not-exist-corpus.json"
    assert not missing.exists()
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "corpus-unreadable"
    assert field(result, "blocked") is True
    assert field(result, "similarity_score") is None
    assert field(result, "gate_version") == "license_scanner@4.0.0-corpus-unreadable"


@pytest.mark.parametrize("case", sorted(INVALID_CORPORA))
def test_invalid_corpus_blocks(tmp_path, monkeypatch, case):
    repo_root = make_repo(tmp_path)
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(INVALID_CORPORA[case], encoding="utf-8")
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False, case
    assert field(result, "reason") == "corpus-invalid", case
    assert field(result, "blocked") is True, case
    assert field(result, "gate_version") == "license_scanner@4.0.0-corpus-invalid", case


class _FakeResponse:
    status = 200

    def read(self, *args, **kwargs):
        return b"{}"

    def getcode(self):
        return 200

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _extract_body(args, kwargs):
    req = args[0] if args else kwargs.get("url")
    data = None
    if len(args) > 1:
        data = args[1]
    if data is None:
        data = kwargs.get("data")
    if data is None and req is not None and not isinstance(req, str):
        data = getattr(req, "data", None)
    if isinstance(data, (bytes, bytearray)):
        data = bytes(data).decode("utf-8")
    return data


def _contains(obj, key, value):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and v == value and type(v) is type(value):
                return True
            if _contains(v, key, value):
                return True
    elif isinstance(obj, list):
        return any(_contains(item, key, value) for item in obj)
    return False


def _contains_value(obj, value):
    if isinstance(obj, dict):
        return any(_contains_value(v, value) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_value(v, value) for v in obj)
    return obj == value


def test_unreadable_corpus_notifies_webhook(tmp_path, monkeypatch):
    repo_root = make_repo(tmp_path)
    missing = repo_root / "does-not-exist-corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/hook")

    calls = []

    def recorder(*args, **kwargs):
        calls.append(_extract_body(args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    if hasattr(license_scanner, "urlopen"):
        monkeypatch.setattr(license_scanner, "urlopen", recorder)

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "corpus-unreadable"
    assert field(result, "blocked") is True
    assert field(result, "notified") is True

    assert calls, "webhook recorder received no call"
    found = False
    for body in calls:
        if body is None:
            continue
        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            continue
        if _contains(payload, "evaluated", False) and _contains_value(payload, "corpus-unreadable"):
            found = True
            break
    assert found, "no webhook payload carried evaluated false and the reason: " + repr(calls)