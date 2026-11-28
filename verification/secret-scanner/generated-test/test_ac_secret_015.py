# hotdocs-criterion: sha256:105e247de7ca22a2609c255ecf42ec80abc7343ffc8196facbedf5eea8fbba27
"""AC-SECRET-015 (covers R-SECRET-012): allowlist entries match exactly
on file, type and SHA-1 of the secret, and on nothing else."""

import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# Built by concatenation so this test file itself holds no detectable key.
ORIGINAL_KEY = "AKIA" + "QQQQRRRRSSSSTTTT"
NEW_KEY = "AKIA" + "ZZZZYYYYXXXXWWWW"

TEST_X = "verification/foo/test_x.py"
OTHER = "verification/foo/other.py"
AWS = "AWS Access Key"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER = (
    "from dataclasses import dataclass\n"
    "from typing import Any\n"
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
    "    return datetime.datetime.now(datetime.timezone.utc).strftime("
    + repr("%Y-%m-%dT%H:%M:%SZ")
    + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {" + repr("entry_count") + ": 0}\n"
)


def _sha1(value):
    return "sha1:" + hashlib.sha1(value.encode("utf-8")).hexdigest()


def _write_allowlist(repo_root, entries):
    data = {"version": 1, "entries": entries}
    raw = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    (repo_root / ".secret-allowlist.json").write_bytes(raw)
    return raw


def _seal(repo_root, raw, number):
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: D" + str(number) + "\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [security-team]\n"
        "last_ratified_commit: 0000000\n"
        "allowlist_sha256: " + digest + "\n"
        "---\n"
        "\n"
        "# D" + str(number) + "\n"
        "\n"
        "Records the hash of the current allowlist.\n"
    )
    (decisions / ("D" + str(number) + ".md")).write_text(text, encoding="utf-8")


def _entry(entry_type=AWS):
    return {
        "file": TEST_X,
        "type": entry_type,
        "hashed_secret": _sha1(ORIGINAL_KEY),
        "reason": "planted-fixture",
    }


def _write_py(repo_root, rel, keys):
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    names = ["K", "J", "L", "M"]
    src = ""
    for i, key in enumerate(keys):
        src += names[i] + " = " + repr(key) + "\n"
    path.write_text(src, encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook call expected")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cm = repo_root / "gen" / "cache-manager"
    cm.mkdir(parents=True)
    (cm / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    # AC-SECRET-014's first scenario: the original key, exactly allowlisted.
    _write_py(repo_root, TEST_X, [ORIGINAL_KEY])
    raw = _write_allowlist(repo_root, [_entry()])
    _seal(repo_root, raw, 1)
    return repo_root


def _matches(result):
    return list(field(result, "matches"))


def _has(items, rule_id, file, line):
    return any(
        field(m, "rule_id") == rule_id
        and field(m, "file") == file
        and field(m, "line") == line
        for m in items
    )


def test_changed_secret_is_not_suppressed(repo):
    _write_py(repo, TEST_X, [NEW_KEY])

    result = secret_scanner.scan(repo)

    assert field(result, "flagged") is True
    matches = _matches(result)
    assert _has(matches, AWS, TEST_X, 1), matches
    assert not any(field(m, "rule_id") == "allowlist-invalid" for m in matches)
    assert list(field(result, "allowed")) == []
    unused = list(field(result, "unused_allowlist_entries"))
    assert any(
        field(e, "file") == TEST_X and field(e, "type") == AWS for e in unused
    ), unused


def test_same_secret_in_other_file_is_not_suppressed(repo):
    _write_py(repo, OTHER, [ORIGINAL_KEY])

    result = secret_scanner.scan(repo)

    matches = _matches(result)
    assert len(matches) == 1, matches
    assert field(matches[0], "file") == OTHER
    assert field(matches[0], "rule_id") == AWS
    assert field(matches[0], "line") == 1
    assert field(result, "flagged") is True
    allowed = list(field(result, "allowed"))
    assert _has(allowed, AWS, TEST_X, 1), allowed


def test_second_line_with_other_secret_is_the_only_match(repo):
    _write_py(repo, TEST_X, [ORIGINAL_KEY, NEW_KEY])

    result = secret_scanner.scan(repo)

    matches = _matches(result)
    assert len(matches) == 1, matches
    assert field(matches[0], "file") == TEST_X
    assert field(matches[0], "line") == 2
    assert field(matches[0], "rule_id") == AWS
    assert field(result, "flagged") is True


def test_entry_with_other_type_does_not_suppress(repo):
    raw = _write_allowlist(repo, [_entry("Hex High Entropy String")])
    _seal(repo, raw, 2)

    result = secret_scanner.scan(repo)

    assert field(result, "flagged") is True
    matches = _matches(result)
    assert _has(matches, AWS, TEST_X, 1), matches
    assert not any(field(m, "rule_id") == "allowlist-invalid" for m in matches)