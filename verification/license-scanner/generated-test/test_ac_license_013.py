# hotdocs-criterion: sha256:f5893348ae5ca0f69b2f17919aef23c9d1fe0fa29e6f6bad3d6a382c8c1065d5
import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest

import license_scanner


VALID_ENTRY = {
    "reference_id": "ref-001",
    "license_family": "GPL",
    "risk_tier": "high",
    "hashes": ["0" * 64],
}


def _f(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


FAKE_CACHE_MANAGER_TEMPLATE = '''
import dataclasses
import datetime
import json

_LOG_PATH = {log_path!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


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


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    _log({{"call": "get", "gate_version": getattr(cache_key, "gate_version", None)}})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log({{"call": "put", "gate_version": getattr(cache_key, "gate_version", None)}})
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}
'''


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # A component source so the scanner has something to look at, should it look.
    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(
        "def add(a, b):\n    total = a + b\n    return total\n\n"
        "def mul(a, b):\n    product = a * b\n    return product\n",
        encoding="utf-8",
    )
    # Fake cache-manager (flat module shape) so no real cache state leaks in.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    log_path = tmp_path / "cache_manager_calls.log"
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_TEMPLATE.format(log_path=str(log_path)),
        encoding="utf-8",
    )
    return repo_root


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    return root


def test_missing_corpus_file_is_unreadable_and_blocks(repo_root, tmp_path, monkeypatch):
    missing = tmp_path / "does-not-exist" / "corpus.json"
    assert not missing.exists()
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _f(result, "evaluated") is False
    assert _f(result, "reason") == "corpus-unreadable"
    assert _f(result, "blocked") is True
    assert _f(result, "similarity_score") is None
    assert _f(result, "gate_version") == "license_scanner@4.0.0-corpus-unreadable"


def _invalid_corpora():
    return [
        ("not-json", "{this is not json"),
        ("json-list", json.dumps([VALID_ENTRY])),
        ("no-entries-list", json.dumps({"corpus_version": 1, "block_threshold": 0.7})),
        (
            "corpus-version-x",
            json.dumps({"corpus_version": "x", "entries": [VALID_ENTRY]}),
        ),
        (
            "block-threshold-0",
            json.dumps({"corpus_version": 1, "block_threshold": 0, "entries": [VALID_ENTRY]}),
        ),
        (
            "block-threshold-1.5",
            json.dumps({"corpus_version": 1, "block_threshold": 1.5, "entries": [VALID_ENTRY]}),
        ),
        (
            "hashes-not-list",
            json.dumps(
                {
                    "corpus_version": 1,
                    "entries": [dict(VALID_ENTRY, hashes="0" * 64)],
                }
            ),
        ),
        (
            "risk-tier-severe",
            json.dumps(
                {
                    "corpus_version": 1,
                    "entries": [dict(VALID_ENTRY, risk_tier="severe")],
                }
            ),
        ),
    ]


@pytest.mark.parametrize(
    "label,content",
    _invalid_corpora(),
    ids=[c[0] for c in _invalid_corpora()],
)
def test_invalid_corpus_blocks(repo_root, tmp_path, monkeypatch, label, content):
    corpus = tmp_path / ("corpus-" + label + ".json")
    corpus.write_text(content, encoding="utf-8")
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _f(result, "evaluated") is False, label
    assert _f(result, "reason") == "corpus-invalid", label
    assert _f(result, "blocked") is True, label
    assert _f(result, "gate_version") == "license_scanner@4.0.0-corpus-invalid", label


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
    if req is not None and not isinstance(req, str):
        data = getattr(req, "data", None)
    if data is None:
        data = kwargs.get("data")
    if data is None and len(args) > 1:
        data = args[1]
    if data is None:
        return ""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data).decode("utf-8", errors="replace")
    return str(data)


def _walk(obj):
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_unreadable_corpus_notifies_webhook(repo_root, tmp_path, monkeypatch):
    missing = tmp_path / "nope" / "corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://webhook.example.invalid/hook")

    calls = []

    def recorder(*args, **kwargs):
        calls.append(_extract_body(args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = license_scanner.scan("comp-foo", repo_root)

    assert _f(result, "evaluated") is False
    assert _f(result, "reason") == "corpus-unreadable"
    assert _f(result, "blocked") is True
    assert _f(result, "notified") is True

    assert calls, "webhook recorder was never called"

    found = False
    for body in calls:
        try:
            parsed = json.loads(body)
        except (ValueError, TypeError):
            parsed = None
        if parsed is not None:
            nodes = list(_walk(parsed))
            has_eval_false = any(
                isinstance(n, dict) and "evaluated" in n and n["evaluated"] is False
                for n in nodes
            )
            has_reason = any(n == "corpus-unreadable" for n in nodes)
            if has_eval_false and has_reason:
                found = True
                break
        else:
            compact = body.replace(" ", "").lower()
            if "corpus-unreadable" in body and (
                '"evaluated":false' in compact or "evaluated=false" in compact
            ):
                found = True
                break
    assert found, "no webhook payload carried evaluated false and the reason: %r" % (calls,)