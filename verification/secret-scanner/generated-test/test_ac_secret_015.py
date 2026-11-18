# hotdocs-criterion: sha256:d1bae7f370922346ca9a78d8d6f05998bad3b370131a711fa4e59587e4766c90
"""AC-SECRET-015 (covers R-SECRET-012): a finding is suppressed only by an
exact allowlist entry (same file, same type, same hashed secret) and by
nothing else.

Every secret-shaped value below is assembled at runtime from short pieces,
so this file never carries a literal that a detector would flag.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


AWS_TYPE = "AWS Access Key"
HEX_TYPE = "Hex High Entropy String"
FIXTURE_FILE = "verification/foo/test_x.py"
OTHER_FILE = "verification/foo/other.py"
ALLOWLIST_NAME = ".secret-allowlist.json"
ORIGINAL_LINE = 3


def _original_key():
    return "AKIA" + "R7TQ" + "2MXV" + "9KPB" + "4WNE"


def _changed_key():
    return "AKIA" + "ZZZZ" + "YYYY" + "XXXX" + "WWWW"


FAKE_CACHE_MANAGER = '''\
"""Stand-in cache-manager: every lookup is a miss, every put is a no-op."""
import datetime
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _sha1(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_source(extra_lines=()):
    lines = ["import os", "", 'K = "' + _original_key() + '"']
    lines.extend(extra_lines)
    return "\n".join(lines) + "\n"


def _entry(entry_type=AWS_TYPE, file=FIXTURE_FILE, secret=None):
    return {
        "file": file,
        "type": entry_type,
        "hashed_secret": "sha1:" + _sha1(secret if secret is not None else _original_key()),
        "reason": "planted-fixture",
    }


def _write_allowlist(repo_root, entries):
    data = {"version": 1, "entries": entries}
    raw = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    (repo_root / ALLOWLIST_NAME).write_bytes(raw)
    return raw


def _seal(repo_root, number):
    raw = (repo_root / ALLOWLIST_NAME).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = (
        "---\n"
        "id: D" + str(number) + "\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [secret-scan-tests]\n"
        "last_ratified_commit: placeholder\n"
        "allowlist_sha256: sha256:" + digest + "\n"
        "---\n"
        "\n"
        "Records the hash of the current secret allowlist.\n"
    )
    _write(repo_root / "specs" / "decisions" / ("D" + str(number) + ".md"), text)


def _build_baseline(repo_root):
    """AC-SECRET-014's first scenario: one planted key, allowlisted, sealed."""
    repo_root.mkdir(parents=True, exist_ok=True)
    _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", FAKE_CACHE_MANAGER)
    _write(repo_root / FIXTURE_FILE, _fixture_source())
    _write_allowlist(repo_root, [_entry()])
    _seal(repo_root, 1)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook call is expected in this test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _build_baseline(root)
    monkeypatch.chdir(root)
    return root


def _run(repo_root):
    result = secret_scanner.scan(Path(repo_root))
    matches = list(_field(result, "matches") or [])
    allowed = list(_field(result, "allowed") or [])
    unused = list(_field(result, "unused_allowlist_entries") or [])
    return result, matches, allowed, unused


def _key(item):
    line = _field(item, "line")
    return (
        _field(item, "rule_id"),
        _field(item, "file"),
        int(line) if line is not None else None,
    )


def _assert_allowlist_valid(matches):
    invalid = [m for m in matches if _field(m, "rule_id") == "allowlist-invalid"]
    assert invalid == [], "the resealed allowlist must stay valid, got %r" % (invalid,)


def test_baseline_fixture_is_clean_and_allowed(repo_root):
    result, matches, allowed, unused = _run(repo_root)
    assert matches == [], matches
    assert _field(result, "flagged") is False
    assert [_key(a) for a in allowed] == [(AWS_TYPE, FIXTURE_FILE, ORIGINAL_LINE)]
    assert unused == []


def test_changed_secret_on_allowlisted_line_is_flagged(repo_root):
    _write(
        repo_root / FIXTURE_FILE,
        "import os\n\nK = \"" + _changed_key() + "\"\n",
    )
    _seal(repo_root, 2)

    result, matches, allowed, unused = _run(repo_root)

    _assert_allowlist_valid(matches)
    assert _field(result, "flagged") is True
    assert [_key(m) for m in matches] == [(AWS_TYPE, FIXTURE_FILE, ORIGINAL_LINE)]
    assert allowed == []
    unused_pairs = [(_field(u, "file"), _field(u, "type")) for u in unused]
    assert (FIXTURE_FILE, AWS_TYPE) in unused_pairs, unused


def test_same_secret_in_another_file_is_flagged(repo_root):
    _write(repo_root / OTHER_FILE, 'K = "' + _original_key() + '"\n')
    _seal(repo_root, 2)

    result, matches, allowed, unused = _run(repo_root)

    _assert_allowlist_valid(matches)
    assert _field(result, "flagged") is True
    assert len(matches) == 1, matches
    assert _field(matches[0], "file") == OTHER_FILE
    assert _field(matches[0], "rule_id") == AWS_TYPE
    assert (AWS_TYPE, FIXTURE_FILE, ORIGINAL_LINE) in [_key(a) for a in allowed]


def test_new_secret_in_allowlisted_file_is_flagged(repo_root):
    _write(
        repo_root / FIXTURE_FILE,
        _fixture_source(extra_lines=['J = "' + _changed_key() + '"']),
    )
    _seal(repo_root, 2)

    result, matches, allowed, unused = _run(repo_root)

    _assert_allowlist_valid(matches)
    assert _field(result, "flagged") is True
    assert [_key(m) for m in matches] == [(AWS_TYPE, FIXTURE_FILE, ORIGINAL_LINE + 1)]
    assert (AWS_TYPE, FIXTURE_FILE, ORIGINAL_LINE) in [_key(a) for a in allowed]


def test_entry_with_different_type_does_not_suppress(repo_root):
    _write_allowlist(repo_root, [_entry(entry_type=HEX_TYPE)])
    _seal(repo_root, 2)

    result, matches, allowed, unused = _run(repo_root)

    _assert_allowlist_valid(matches)
    assert _field(result, "flagged") is True
    original = (AWS_TYPE, FIXTURE_FILE, ORIGINAL_LINE)
    assert original in [_key(m) for m in matches], matches
    assert original not in [_key(a) for a in allowed], allowed