# hotdocs-criterion: sha256:9b078e3aca848a56fe18effc0b1cdf6d1041bd62abafff3b8e5da24e15b725af
import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


SECRET = "AKIA" + "ABCDEFGHIJKLMNOP"
TARGET_FILE = "verification/foo/t.py"
RULE = "AWS Access Key"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER = (
    "import dataclasses\n"
    "import datetime\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
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
    "@dataclasses.dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    payload = result['payload'] if isinstance(result, dict) else getattr(result, 'payload')\n"
    "    for key in ('scope', 'gate_version', 'flagged', 'matches'):\n"
    "        present = key in payload if isinstance(payload, dict) else hasattr(payload, key)\n"
    "        if not present:\n"
    "            raise SchemaValidationError('missing payload key ' + key)\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return dict(entry_count=0)\n"
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("urlopen must not be called in this test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)


def _allowlist_bytes(entries):
    doc = {"version": 1, "entries": entries}
    return (json.dumps(doc, indent=2) + "\n").encode("utf-8")


def _valid_entry():
    return {
        "file": TARGET_FILE,
        "type": RULE,
        "hashed_secret": "sha1:" + hashlib.sha1(SECRET.encode("utf-8")).hexdigest(),
        "reason": "planted-fixture",
    }


def _seal_of(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write_decision(repo_root, number, status, allowlist_hash):
    d = repo_root / "specs" / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        + "id: D" + str(number) + "\n"
        + "title: Seal the secret allowlist\n"
        + "status: " + status + "\n"
        + "owners: [security-team]\n"
    )
    if status == "ratified":
        text += "last_ratified_commit: 0000000\n"
    if allowlist_hash is not None:
        text += "allowlist_sha256: " + allowlist_hash + "\n"
    text += "---\n\n# D" + str(number) + "\n\nRecords the allowlist seal.\n"
    (d / ("D" + str(number) + ".md")).write_text(text, encoding="utf-8")


def _build_repo(repo_root, allowlist_data):
    target = repo_root / TARGET_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("K = " + repr(SECRET).replace("'", '"') + "\n", encoding="utf-8")

    cm = repo_root / "gen" / "cache-manager"
    cm.mkdir(parents=True, exist_ok=True)
    (cm / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    if allowlist_data is not None:
        (repo_root / ".secret-allowlist.json").write_bytes(allowlist_data)


def _matches(result):
    return list(field(result, "matches"))


def _invalid_matches(result):
    return [m for m in _matches(result) if field(m, "rule_id") == "allowlist-invalid"]


def _target_matches(result, collection):
    return [
        m for m in collection
        if field(m, "rule_id") == RULE and field(m, "file") == TARGET_FILE
    ]


def test_sealed_valid_allowlist_allows_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    data = _allowlist_bytes([_valid_entry()])
    _build_repo(repo_root, data)
    _write_decision(repo_root, 1, "ratified", _seal_of(data))

    result = secret_scanner.scan(repo_root)

    allowed = list(field(result, "allowed"))
    hits = _target_matches(result, allowed)
    assert len(hits) == 1, allowed
    assert field(hits[0], "line") == 1
    assert field(result, "flagged") is False
    assert _matches(result) == []
    assert _invalid_matches(result) == []


CASES = ["allowlist_one_byte_changed", "d1_hash_changed", "d1_not_ratified",
         "no_decision", "ratified_d2_other_hash"]


@pytest.mark.parametrize("case", CASES)
def test_unsealed_allowlist_is_invalid(tmp_path, case):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    data = _allowlist_bytes([_valid_entry()])
    good_seal = _seal_of(data)
    other_seal = _seal_of(data + b" ")
    assert other_seal != good_seal

    if case == "allowlist_one_byte_changed":
        changed = data[:-1] + b" "
        assert len(changed) == len(data) and changed != data
        json.loads(changed.decode("utf-8"))
        _build_repo(repo_root, changed)
        _write_decision(repo_root, 1, "ratified", good_seal)
    elif case == "d1_hash_changed":
        _build_repo(repo_root, data)
        _write_decision(repo_root, 1, "ratified", other_seal)
    elif case == "d1_not_ratified":
        _build_repo(repo_root, data)
        _write_decision(repo_root, 1, "draft", good_seal)
    elif case == "no_decision":
        _build_repo(repo_root, data)
    elif case == "ratified_d2_other_hash":
        _build_repo(repo_root, data)
        _write_decision(repo_root, 1, "ratified", good_seal)
        _write_decision(repo_root, 2, "ratified", other_seal)
    else:
        raise AssertionError(case)

    result = secret_scanner.scan(repo_root)
    matches = _matches(result)

    reported = _target_matches(result, matches)
    assert len(reported) == 1, matches
    assert field(reported[0], "line") == 1

    invalid = _invalid_matches(result)
    assert len(invalid) == 1, matches
    assert field(invalid[0], "risk_tier") == "high"
    assert field(invalid[0], "file") == ".secret-allowlist.json"
    assert field(invalid[0], "line") == 1

    assert _target_matches(result, list(field(result, "allowed"))) == []
    assert field(result, "flagged") is True


def test_empty_allowlist_without_decision_is_not_invalid(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    data = _allowlist_bytes([])
    _build_repo(repo_root, data)

    result = secret_scanner.scan(repo_root)

    assert _invalid_matches(result) == []
    reported = _target_matches(result, _matches(result))
    assert len(reported) == 1
    assert field(result, "flagged") is True