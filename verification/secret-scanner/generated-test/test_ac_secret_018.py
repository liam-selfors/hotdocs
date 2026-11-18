# hotdocs-criterion: sha256:4eed23423f0512281c01425206bc551c3f5df5584c5f0117d841d7037effc877
"""AC-SECRET-018 (covers R-SECRET-012): the allowlist is honored only when
sealed by the highest-numbered ratified decision carrying its exact SHA-256;
otherwise it is invalid as a whole and an allowlist-invalid match is added.
An allowlist with zero entries needs no seal.
"""

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# A faithful stand-in for comp-cache-manager's documented library contract.
# It always reports a miss, so every scan below is a fresh scan. It holds no
# long random-looking literal and no temporary-directory path.
_FAKE_CACHE_MANAGER = r'''
from dataclasses import dataclass
from datetime import datetime, timezone


class SchemaValidationError(ValueError):
    pass


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
        return 0

    def __repr__(self):
        return "Miss()"


_REQUIRED = {
    "generator": ("component_id", "model", "prompt_version", "files"),
    "compiler": ("outputs", "gate_version", "summary"),
    "generated_test": ("component_id", "criterion_id", "model", "file"),
    "llm_judge": ("result", "rationale"),
    "license_scanner": ("component_id", "gate_version", "similarity_score", "blocked", "matches"),
    "secret_scanner": ("scope", "gate_version", "flagged", "matches"),
}


def _read(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_version = _read(cache_key, "gate_version") or ""
    key_type = str(gate_version).split("@", 1)[0]
    gate_type = _read(result, "gate_type")
    if gate_type not in _REQUIRED or gate_type != key_type:
        raise SchemaValidationError("gate type mismatch")
    payload = _read(result, "payload")
    if payload is None:
        raise SchemaValidationError("missing payload")
    for name in _REQUIRED[gate_type]:
        if isinstance(payload, dict):
            present = name in payload
        else:
            present = hasattr(payload, name)
        if not present:
            raise SchemaValidationError("missing payload key " + name)
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _secret():
    # Built at runtime so this test file itself embeds no detectable key.
    return "AKIA" + "ABCDEFGHIJKLMNOP"


def _entry():
    return {
        "file": "verification/foo/t.py",
        "type": "AWS Access Key",
        "hashed_secret": "sha1:" + hashlib.sha1(_secret().encode("utf-8")).hexdigest(),
        "reason": "planted-fixture",
    }


def _allowlist_bytes(entries):
    return (json.dumps({"version": 1, "entries": entries}, indent=2) + "\n").encode("utf-8")


def _seal(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _decision_text(n, status, allowlist_sha):
    lines = [
        "---",
        "id: D%d" % n,
        "title: Seal the scanner allowlist %d" % n,
        "status: %s" % status,
        "owners: [secops]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000")
    if allowlist_sha is not None:
        lines.append("allowlist_sha256: %s" % allowlist_sha)
    lines += ["---", "", "# D%d" % n, "", "Records the allowlist seal.", ""]
    return "\n".join(lines)


def _build_repo(root, allowlist_bytes, decisions):
    root.mkdir(parents=True, exist_ok=True)
    fixture_dir = root / "verification" / "foo"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "t.py").write_bytes(('K = "%s"\n' % _secret()).encode("utf-8"))
    if allowlist_bytes is not None:
        (root / ".secret-allowlist.json").write_bytes(allowlist_bytes)
    if decisions:
        dec_dir = root / "specs" / "decisions"
        dec_dir.mkdir(parents=True, exist_ok=True)
        for n, status, allowlist_sha in decisions:
            (dec_dir / ("D%d.md" % n)).write_bytes(
                _decision_text(n, status, allowlist_sha).encode("utf-8")
            )
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(_FAKE_CACHE_MANAGER, encoding="utf-8")
    return root


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise urllib.error.URLError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _matches(result):
    return list(_field(result, "matches") or [])


def _allowed(result):
    return list(_field(result, "allowed") or [])


def _is_fixture_finding(item):
    return (
        _field(item, "rule_id") == "AWS Access Key"
        and _field(item, "file") == "verification/foo/t.py"
        and _field(item, "line") == 1
    )


def _invalid_matches(result):
    return [m for m in _matches(result) if _field(m, "rule_id") == "allowlist-invalid"]


def test_sealed_valid_allowlist_suppresses_finding(env):
    allowlist = _allowlist_bytes([_entry()])
    repo = _build_repo(env / "repo", allowlist, [(1, "ratified", _seal(allowlist))])

    result = secret_scanner.scan(Path(repo))

    allowed = _allowed(result)
    assert any(_is_fixture_finding(a) for a in allowed), allowed
    matches = _matches(result)
    assert not any(_is_fixture_finding(m) for m in matches), matches
    assert _invalid_matches(result) == [], matches
    assert _field(result, "flagged") is False, matches
    unused = list(_field(result, "unused_allowlist_entries") or [])
    assert not any(
        _field(u, "file") == "verification/foo/t.py" and _field(u, "type") == "AWS Access Key"
        for u in unused
    ), unused


def _case_one_byte_changed():
    original = _allowlist_bytes([_entry()])
    return original + b"\n", [(1, "ratified", _seal(original))]


def _case_d1_hash_changed():
    allowlist = _allowlist_bytes([_entry()])
    return allowlist, [(1, "ratified", _seal(b"some other allowlist bytes"))]


def _case_d1_not_ratified():
    allowlist = _allowlist_bytes([_entry()])
    return allowlist, [(1, "draft", _seal(allowlist))]


def _case_no_decision():
    return _allowlist_bytes([_entry()]), []


def _case_ratified_d2_other_hash():
    allowlist = _allowlist_bytes([_entry()])
    return allowlist, [
        (1, "ratified", _seal(allowlist)),
        (2, "ratified", _seal(b"a different allowlist entirely")),
    ]


@pytest.mark.parametrize(
    "case",
    [
        _case_one_byte_changed,
        _case_d1_hash_changed,
        _case_d1_not_ratified,
        _case_no_decision,
        _case_ratified_d2_other_hash,
    ],
    ids=[
        "allowlist-changed-by-one-byte",
        "d1-hash-changed",
        "d1-not-ratified",
        "no-decision",
        "ratified-d2-other-hash",
    ],
)
def test_unsealed_allowlist_is_invalid(env, case):
    allowlist, decisions = case()
    repo = _build_repo(env / "repo", allowlist, decisions)

    result = secret_scanner.scan(Path(repo))

    matches = _matches(result)
    assert any(_is_fixture_finding(m) for m in matches), matches
    assert not any(_is_fixture_finding(a) for a in _allowed(result)), _allowed(result)

    invalid = _invalid_matches(result)
    assert len(invalid) == 1, matches
    only = invalid[0]
    assert _field(only, "risk_tier") == "high"
    assert _field(only, "file") == ".secret-allowlist.json"
    assert _field(only, "line") == 1

    assert _field(result, "flagged") is True


def test_zero_entry_allowlist_without_decision_is_not_invalid(env):
    allowlist = _allowlist_bytes([])
    repo = _build_repo(env / "repo", allowlist, [])

    result = secret_scanner.scan(Path(repo))

    matches = _matches(result)
    assert _invalid_matches(result) == [], matches
    assert any(_is_fixture_finding(m) for m in matches), matches
    assert not any(_is_fixture_finding(a) for a in _allowed(result)), _allowed(result)