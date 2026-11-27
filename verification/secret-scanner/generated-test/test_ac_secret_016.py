# hotdocs-criterion: sha256:838628bc48f7d1c804cf7121668b19047163caa844022a31794b2ee8a236415d
"""AC-SECRET-016 (covers R-SECRET-012): a corrupt allowlist fails closed.

Each scenario builds a fresh repo holding two planted AWS keys, an
otherwise valid allowlist for the one under verification/, sealed by a
ratified decision, then applies exactly one corruption and re-seals it.
Each scenario expects:

- every finding to be reported, and
- one extra "allowlist-invalid" match.
"""

import hashlib
import json
import urllib.request

import pytest

import secret_scanner


# Built by concatenation so this test file itself holds no detectable key.
SECRET = "AKIA" + "ABCDEFGHIJKLMNOP"
EXTRA_SECRET = "AKIA" + "ZZZZYYYYXXXXWWWW"
SECRET_SHA1 = hashlib.sha1(SECRET.encode("utf-8")).hexdigest()

TEST_FILE = "verification/foo/test_x.py"
GEN_FILE = "gen/foo/c.py"
ALLOWLIST = ".secret-allowlist.json"
AWS = "AWS Access Key"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER = (
    "import datetime\n"
    "from dataclasses import dataclass\n"
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
    "    now = datetime.datetime.now(datetime.timezone.utc)\n"
    "    return now.strftime(" + repr("%Y-%m-%dT%H:%M:%SZ") + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {" + repr("entry_count") + ": 0}\n"
)


def valid_entry(**overrides):
    entry = {
        "file": TEST_FILE,
        "type": AWS,
        "hashed_secret": "sha1:" + SECRET_SHA1,
        "reason": "planted-fixture",
    }
    entry.update(overrides)
    return entry


def doc(obj):
    return json.dumps(obj, indent=2).encode("utf-8")


def valid_allowlist_bytes():
    return doc({"version": 1, "entries": [valid_entry()]})


def write_seal(repo_root, allowlist_bytes):
    digest = hashlib.sha256(allowlist_bytes).hexdigest()
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: D1\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "last_ratified_commit: 0000000\n"
        "allowlist_sha256: sha256:" + digest + "\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "Records the hash of the secret allowlist.\n"
    )
    (decisions / "D1.md").write_text(text, encoding="utf-8")


def build_repo(repo_root, allowlist_bytes):
    for rel in (TEST_FILE, GEN_FILE):
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("K = " + json.dumps(SECRET) + "\n", encoding="utf-8")

    # A cache-manager stand-in that always misses, so every scan is fresh.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    if allowlist_bytes is not None:
        (repo_root / ALLOWLIST).write_bytes(allowlist_bytes)
        write_seal(repo_root, allowlist_bytes)


@pytest.fixture(autouse=True)
def no_webhook(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def refuse(*args, **kwargs):
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def has_match(matches, rule_id, file):
    return any(
        field(m, "rule_id") == rule_id and field(m, "file") == file for m in matches
    )


def invalid_matches(matches):
    return [m for m in matches if field(m, "rule_id") == "allowlist-invalid"]


# ---------------------------------------------------------------------------
# Control: the unbroken, sealed allowlist is honored, so only the corruption
# below can be what invalidates it.
# ---------------------------------------------------------------------------


def test_control_valid_sealed_allowlist_is_honored(tmp_path):
    build_repo(tmp_path, valid_allowlist_bytes())
    result = secret_scanner.scan(tmp_path)
    matches = field(result, "matches")
    allowed = field(result, "allowed")

    assert invalid_matches(matches) == []
    assert has_match(matches, AWS, GEN_FILE)
    assert not has_match(matches, AWS, TEST_FILE)
    assert any(
        field(a, "rule_id") == AWS and field(a, "file") == TEST_FILE for a in allowed
    )


# ---------------------------------------------------------------------------
# Corruptions
# ---------------------------------------------------------------------------


def _missing_key_entry():
    entry = valid_entry()
    del entry["reason"]
    return entry


CORRUPTIONS = {
    "not-json": b'{"version": 1, "entries": [',
    "extra-top-level-key": doc(
        {"version": 1, "entries": [valid_entry()], "extra": "x"}
    ),
    "version-2": doc({"version": 2, "entries": [valid_entry()]}),
    "entry-extra-key": doc(
        {"version": 1, "entries": [dict(valid_entry(), note="x")]}
    ),
    "entry-missing-key": doc({"version": 1, "entries": [_missing_key_entry()]}),
    "reason-other": doc({"version": 1, "entries": [valid_entry(reason="other")]}),
    "hash-no-sha1-prefix": doc(
        {"version": 1, "entries": [valid_entry(hashed_secret=SECRET_SHA1)]}
    ),
    "file-dotdot": doc({"version": 1, "entries": [valid_entry(file="../x.py")]}),
    "file-absolute": doc({"version": 1, "entries": [valid_entry(file="/etc/x")]}),
    "file-pattern": doc(
        {"version": 1, "entries": [valid_entry(file="verification/*.py")]}
    ),
    "planted-fixture-outside-verification": doc(
        {"version": 1, "entries": [valid_entry(file=GEN_FILE)]}
    ),
    "public-constant-for-aws": doc(
        {"version": 1, "entries": [valid_entry(reason="public-constant")]}
    ),
    "valid-entry-beside-corrupt": doc(
        {
            "version": 1,
            "entries": [valid_entry(), valid_entry(file=GEN_FILE, reason="other")],
        }
    ),
}


def assert_fails_closed(result):
    matches = field(result, "matches")

    assert field(result, "flagged") is True
    assert has_match(matches, AWS, TEST_FILE), matches
    assert has_match(matches, AWS, GEN_FILE), matches

    invalid = invalid_matches(matches)
    assert len(invalid) == 1, matches
    only = invalid[0]
    assert field(only, "risk_tier") == "high"
    assert field(only, "file") == ALLOWLIST
    assert field(only, "line") == 1

    # No entry is honored.
    assert not any(
        field(a, "file") == TEST_FILE for a in field(result, "allowed")
    )


@pytest.mark.parametrize(
    "allowlist_bytes",
    list(CORRUPTIONS.values()),
    ids=list(CORRUPTIONS.keys()),
)
def test_corrupt_allowlist_fails_closed(tmp_path, allowlist_bytes):
    build_repo(tmp_path, allowlist_bytes)
    result = secret_scanner.scan(tmp_path)
    assert_fails_closed(result)


def test_allowlist_is_scanned_like_any_file(tmp_path):
    allowlist_bytes = doc(
        {"version": 1, "entries": [valid_entry()], "extra": EXTRA_SECRET}
    )
    build_repo(tmp_path, allowlist_bytes)
    result = secret_scanner.scan(tmp_path)

    assert_fails_closed(result)
    assert has_match(field(result, "matches"), AWS, ALLOWLIST), field(
        result, "matches"
    )


# ---------------------------------------------------------------------------
# Absent allowlist
# ---------------------------------------------------------------------------


def test_absent_allowlist_allows_nothing_and_is_not_invalid(tmp_path):
    build_repo(tmp_path, None)
    assert not (tmp_path / ALLOWLIST).exists()

    result = secret_scanner.scan(tmp_path)
    matches = field(result, "matches")

    assert field(result, "flagged") is True
    assert invalid_matches(matches) == []
    assert list(field(result, "allowed")) == []