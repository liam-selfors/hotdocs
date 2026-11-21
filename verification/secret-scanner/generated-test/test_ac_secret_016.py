# hotdocs-criterion: sha256:90065a53b9991560e1c1b66fc612f1dbbc6991c94bce1698b84f02d0b10418e5
import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


SECRET = "AKIAABCDEFGHIJKLMNOP"
EXTRA_SECRET = "AKIAZZZZYYYYXXXXWWWW"
AWS = "AWS Access Key"
TEST_FILE = "verification/foo/test_x.py"
GEN_FILE = "gen/foo/c.py"
ALLOWLIST = ".secret-allowlist.json"
HASHED = "sha1:" + hashlib.sha1(SECRET.encode("utf-8")).hexdigest()


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER = (
    "from dataclasses import dataclass\n"
    "from datetime import datetime, timezone\n"
    "from typing import Any\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: Any\n"
    "    stored_at: str\n"
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
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return dict(entry_count=0)\n"
    "\n"
    "\n"
    "def main(argv=None):\n"
    "    return 0\n"
)


def valid_entry():
    return {
        "file": TEST_FILE,
        "type": AWS,
        "hashed_secret": HASHED,
        "reason": "planted-fixture",
    }


def valid_allowlist():
    return {"version": 1, "entries": [valid_entry()]}


def dump(obj):
    return (json.dumps(obj, indent=2) + "\n").encode("utf-8")


def build_repo(root: Path):
    (root / "verification" / "foo").mkdir(parents=True)
    (root / "gen" / "foo").mkdir(parents=True)
    line = "K = " + json.dumps(SECRET) + "\n"
    (root / TEST_FILE).write_text(line, encoding="utf-8")
    (root / GEN_FILE).write_text(line, encoding="utf-8")
    cm = root / "gen" / "cache-manager"
    cm.mkdir(parents=True)
    (cm / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")


def seal(root: Path, data: bytes):
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    decisions = root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: D1\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [security-team]\n"
        "last_ratified_commit: 0000000\n"
        "allowlist_sha256: " + digest + "\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "Records the hash of the allowlist.\n"
    )
    (decisions / "D1.md").write_text(text, encoding="utf-8")


def write_allowlist(root: Path, data: bytes):
    (root / ALLOWLIST).write_bytes(data)
    seal(root, data)


@pytest.fixture(autouse=True)
def no_webhook(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def fake_urlopen(*args, **kwargs):
        raise AssertionError("webhook must not be called")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", fake_urlopen)


# --- corruptions ----------------------------------------------------------

def c_not_json():
    return b'{"version": 1, "entries": [\n'


def c_top_extra_key():
    d = valid_allowlist()
    d["extra"] = "x"
    return dump(d)


def c_version_2():
    d = valid_allowlist()
    d["version"] = 2
    return dump(d)


def c_entry_extra_key():
    d = valid_allowlist()
    d["entries"][0]["note"] = "x"
    return dump(d)


def c_entry_missing_key():
    d = valid_allowlist()
    del d["entries"][0]["reason"]
    return dump(d)


def c_reason_other():
    d = valid_allowlist()
    d["entries"][0]["reason"] = "other"
    return dump(d)


def c_no_sha1_prefix():
    d = valid_allowlist()
    d["entries"][0]["hashed_secret"] = HASHED[len("sha1:"):]
    return dump(d)


def c_file_dotdot():
    d = valid_allowlist()
    d["entries"][0]["file"] = "../x.py"
    return dump(d)


def c_file_absolute():
    d = valid_allowlist()
    d["entries"][0]["file"] = "/etc/x"
    return dump(d)


def c_file_pattern():
    d = valid_allowlist()
    d["entries"][0]["file"] = "verification/*.py"
    return dump(d)


def c_planted_fixture_in_gen():
    d = valid_allowlist()
    d["entries"][0]["file"] = GEN_FILE
    return dump(d)


def c_public_constant_aws():
    d = valid_allowlist()
    d["entries"][0]["reason"] = "public-constant"
    return dump(d)


def c_valid_beside_corrupt():
    d = valid_allowlist()
    bad = valid_entry()
    bad["file"] = GEN_FILE
    bad["reason"] = "other"
    d["entries"].append(bad)
    return dump(d)


def c_extra_key_with_secret():
    d = valid_allowlist()
    d["extra"] = EXTRA_SECRET
    return dump(d)


CORRUPTIONS = [
    ("not-json", c_not_json),
    ("top-level-extra-key", c_top_extra_key),
    ("version-2", c_version_2),
    ("entry-extra-key", c_entry_extra_key),
    ("entry-missing-key", c_entry_missing_key),
    ("reason-other", c_reason_other),
    ("hash-no-sha1-prefix", c_no_sha1_prefix),
    ("file-dotdot", c_file_dotdot),
    ("file-absolute", c_file_absolute),
    ("file-pattern", c_file_pattern),
    ("planted-fixture-in-gen", c_planted_fixture_in_gen),
    ("public-constant-aws", c_public_constant_aws),
    ("valid-beside-corrupt", c_valid_beside_corrupt),
    ("extra-key-with-secret", c_extra_key_with_secret),
]


def has_match(matches, rule_id, file):
    return any(
        field(m, "rule_id") == rule_id and field(m, "file") == file
        for m in matches
    )


def test_control_valid_sealed_allowlist_is_honored(tmp_path):
    build_repo(tmp_path)
    write_allowlist(tmp_path, dump(valid_allowlist()))
    result = secret_scanner.scan(tmp_path)
    matches = list(field(result, "matches"))
    assert not any(field(m, "rule_id") == "allowlist-invalid" for m in matches)
    assert not has_match(matches, AWS, TEST_FILE)
    assert has_match(matches, AWS, GEN_FILE)
    allowed = list(field(result, "allowed"))
    assert any(field(a, "file") == TEST_FILE for a in allowed)


@pytest.mark.parametrize(
    "make", [c[1] for c in CORRUPTIONS], ids=[c[0] for c in CORRUPTIONS]
)
def test_corrupt_allowlist_fails_closed(tmp_path, make):
    build_repo(tmp_path)
    write_allowlist(tmp_path, make())

    result = secret_scanner.scan(tmp_path)
    matches = list(field(result, "matches"))

    assert field(result, "flagged") is True
    assert has_match(matches, AWS, TEST_FILE), matches
    assert has_match(matches, AWS, GEN_FILE), matches

    invalid = [m for m in matches if field(m, "rule_id") == "allowlist-invalid"]
    assert len(invalid) == 1, matches
    m = invalid[0]
    assert field(m, "risk_tier") == "high"
    assert field(m, "file") == ALLOWLIST
    assert field(m, "line") == 1

    allowed = list(field(result, "allowed"))
    assert allowed == []

    if make is c_extra_key_with_secret:
        assert has_match(matches, AWS, ALLOWLIST), matches


def test_absent_allowlist_allows_nothing(tmp_path):
    build_repo(tmp_path)
    assert not (tmp_path / ALLOWLIST).exists()

    result = secret_scanner.scan(tmp_path)
    matches = list(field(result, "matches"))

    assert field(result, "flagged") is True
    assert not any(field(m, "rule_id") == "allowlist-invalid" for m in matches)
    assert list(field(result, "allowed")) == []
    assert has_match(matches, AWS, TEST_FILE)
    assert has_match(matches, AWS, GEN_FILE)