import hashlib
import json

import pytest
import urllib.request

import secret_scanner


SECRET = "AKIAABCDEFGHIJKLMNOP"
RULE_ID = "AWS Access Key"


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _sha1(value):
    return "sha1:" + hashlib.sha1(value.encode()).hexdigest()


def _write_cache_manager_stub(repo_root):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(
        "class _Miss:\n"
        "    payload = None\n"
        "\n"
        "def get(cache_key, repo_root=None):\n"
        "    return _Miss()\n"
        "\n"
        "def put(cache_key, result, repo_root=None):\n"
        "    pass\n"
        "\n"
        "class CacheKey:\n"
        "    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,"
        " gate_version=None, model_pin=None):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_inputs_hash = gate_inputs_hash\n"
        "        self.gate_version = gate_version\n"
        "        self.model_pin = model_pin\n"
        "\n"
        "class CachedResult:\n"
        "    def __init__(self, gate_type=None, payload=None, stored_at=None):\n"
        "        self.gate_type = gate_type\n"
        "        self.payload = payload\n"
        "        self.stored_at = stored_at\n"
    )


def _base_repo(tmp_path, name):
    repo_root = tmp_path / name
    repo_root.mkdir()
    _write_cache_manager_stub(repo_root)
    return repo_root


def _write_secret_file(repo_root):
    target = repo_root / "verification" / "foo"
    target.mkdir(parents=True, exist_ok=True)
    (target / "t.py").write_text('K = "%s"\n' % SECRET)


def _allowed_entry():
    return {
        "file": "verification/foo/t.py",
        "type": RULE_ID,
        "hashed_secret": _sha1(SECRET),
        "reason": "planted-fixture",
    }


def _write_allowlist(repo_root, entries):
    data = {"version": 1, "entries": entries}
    (repo_root / ".secret-allowlist.json").write_text(json.dumps(data, indent=2))
    return (repo_root / ".secret-allowlist.json").read_bytes()


def _write_decision(repo_root, number, status, allowlist_sha256_hex):
    decisions_dir = repo_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "id: D%d" % number,
        "title: Seal the allowlist",
        "status: %s" % status,
        "owners: [alice]",
    ]
    if status == "ratified":
        lines.append('last_ratified_commit: "0000000"')
    if allowlist_sha256_hex is not None:
        lines.append("allowlist_sha256: sha256:%s" % allowlist_sha256_hex)
    lines.append("---")
    lines.append("")
    lines.append("Decision body text.")
    (decisions_dir / ("D%d.md" % number)).write_text("\n".join(lines))


def _assert_invalid(result):
    assert _field(result, "flagged") is True

    matches = _field(result, "matches") or []
    rule_ids = [_field(m, "rule_id") for m in matches]
    assert RULE_ID in rule_ids
    assert "allowlist-invalid" in rule_ids

    invalid_matches = [m for m in matches if _field(m, "rule_id") == "allowlist-invalid"]
    assert len(invalid_matches) == 1
    invalid = invalid_matches[0]
    assert _field(invalid, "risk_tier") == "high"
    assert _field(invalid, "file") == ".secret-allowlist.json"
    assert _field(invalid, "line") == 1

    allowed = _field(result, "allowed") or []
    assert RULE_ID not in [_field(a, "rule_id") for a in allowed]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # An AWS Access Key match is "high" risk, which could otherwise trigger a
    # real webhook POST if the environment happens to have the compliance
    # webhook var set; guard against any live network call regardless.
    def _fail(*args, **kwargs):
        raise AssertionError("unexpected network call")

    monkeypatch.setattr(urllib.request, "urlopen", _fail)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)


def test_sealed_allowlist_suppresses_finding(tmp_path):
    repo_root = _base_repo(tmp_path, "sealed_ok")
    _write_secret_file(repo_root)
    allowlist_bytes = _write_allowlist(repo_root, [_allowed_entry()])
    seal = hashlib.sha256(allowlist_bytes).hexdigest()
    _write_decision(repo_root, 1, "ratified", seal)

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is False

    allowed = _field(result, "allowed") or []
    assert RULE_ID in [_field(a, "rule_id") for a in allowed]

    matches = _field(result, "matches") or []
    assert matches == []


def test_allowlist_edited_after_seal_invalidates(tmp_path):
    repo_root = _base_repo(tmp_path, "byte_changed")
    _write_secret_file(repo_root)
    allowlist_bytes = _write_allowlist(repo_root, [_allowed_entry()])
    seal = hashlib.sha256(allowlist_bytes).hexdigest()
    _write_decision(repo_root, 1, "ratified", seal)

    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_path.write_bytes(allowlist_bytes + b" ")

    result = secret_scanner.scan(repo_root)
    _assert_invalid(result)


def test_decision_hash_mismatch_invalidates(tmp_path):
    repo_root = _base_repo(tmp_path, "hash_mismatch")
    _write_secret_file(repo_root)
    allowlist_bytes = _write_allowlist(repo_root, [_allowed_entry()])
    real_seal = hashlib.sha256(allowlist_bytes).hexdigest()
    wrong_seal = ("1" if real_seal[0] == "0" else "0") + real_seal[1:]
    _write_decision(repo_root, 1, "ratified", wrong_seal)

    result = secret_scanner.scan(repo_root)
    _assert_invalid(result)


def test_decision_not_ratified_invalidates(tmp_path):
    repo_root = _base_repo(tmp_path, "not_ratified")
    _write_secret_file(repo_root)
    allowlist_bytes = _write_allowlist(repo_root, [_allowed_entry()])
    seal = hashlib.sha256(allowlist_bytes).hexdigest()
    _write_decision(repo_root, 1, "draft", seal)

    result = secret_scanner.scan(repo_root)
    _assert_invalid(result)


def test_no_decision_invalidates(tmp_path):
    repo_root = _base_repo(tmp_path, "no_decision")
    _write_secret_file(repo_root)
    _write_allowlist(repo_root, [_allowed_entry()])

    result = secret_scanner.scan(repo_root)
    _assert_invalid(result)


def test_other_decision_wrong_hash_invalidates(tmp_path):
    repo_root = _base_repo(tmp_path, "other_decision")
    _write_secret_file(repo_root)
    _write_allowlist(repo_root, [_allowed_entry()])
    other_seal = hashlib.sha256(b"unrelated content").hexdigest()
    _write_decision(repo_root, 2, "ratified", other_seal)

    result = secret_scanner.scan(repo_root)
    _assert_invalid(result)


def test_empty_allowlist_no_decision_is_valid(tmp_path):
    repo_root = _base_repo(tmp_path, "empty_allowlist")
    _write_allowlist(repo_root, [])

    result = secret_scanner.scan(repo_root)

    matches = _field(result, "matches") or []
    rule_ids = [_field(m, "rule_id") for m in matches]
    assert "allowlist-invalid" not in rule_ids