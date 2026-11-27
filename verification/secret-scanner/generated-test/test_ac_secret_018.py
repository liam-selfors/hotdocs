# hotdocs-criterion: sha256:6c22a81f577ceaa15c3fd9bec9ce26c2a7bd03aaef7c7a30dd00da338531d441
"""AC-SECRET-018 (covers R-SECRET-012): a populated allowlist is honored only
when sealed by the highest-numbered ratified decision carrying
`allowlist_sha256`; otherwise it fails closed with one allowlist-invalid match.
An allowlist with zero entries needs no seal."""

import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


FIXTURE_FILE = "verification/foo/t.py"
# Assembled from parts so this test file carries no contiguous key literal.
SECRET = "AKIA" + "ABCDEFGHIJKLMNOP"
RULE = "AWS Access Key"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_LINES = [
    "from dataclasses import dataclass",
    "import datetime",
    "",
    "",
    "@dataclass",
    "class CacheKey:",
    "    spec_bundle_hash: str",
    "    gate_inputs_hash: str",
    "    gate_version: str",
    "    model_pin: str",
    "",
    "",
    "@dataclass",
    "class CachedResult:",
    "    gate_type: str",
    "    payload: dict",
    "    stored_at: str",
    "",
    "",
    "class Miss:",
    "    def __eq__(self, other):",
    "        return isinstance(other, Miss)",
    "",
    "    def __hash__(self):",
    "        return 0",
    "",
    "",
    "class SchemaValidationError(ValueError):",
    "    pass",
    "",
    "",
    "def get(cache_key, *, repo_root=None):",
    "    return Miss()",
    "",
    "",
    "def put(cache_key, result, *, repo_root=None):",
    "    return None",
    "",
    "",
    "def now_iso():",
    "    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)",
    "    return now.isoformat().replace('+00:00', 'Z')",
    "",
    "",
    "def stats(*, repo_root=None):",
    "    return {'entry_count': 0}",
    "",
]


def write_fake_cache_manager(repo):
    d = repo / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text("\n".join(FAKE_CACHE_MANAGER_LINES))


def write_fixture_file(repo):
    p = repo / FIXTURE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("K = " + json.dumps(SECRET) + "\n")


def allowlist_bytes(entries):
    return (json.dumps({"version": 1, "entries": entries}, indent=2) + "\n").encode("utf-8")


def valid_entry():
    return {
        "file": FIXTURE_FILE,
        "type": RULE,
        "hashed_secret": "sha1:" + hashlib.sha1(SECRET.encode("utf-8")).hexdigest(),
        "reason": "planted-fixture",
    }


def seal_of(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write_decision(repo, number, status, allowlist_hash):
    d = repo / "specs" / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "id: D" + str(number),
        "title: Seal the secret allowlist",
        "status: " + status,
        "owners: [security-team]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000")
    lines.append("allowlist_sha256: " + allowlist_hash)
    lines += [
        "---",
        "",
        "# D" + str(number),
        "",
        "Records the hash of the secret allowlist.",
        "",
    ]
    (d / ("D" + str(number) + ".md")).write_text("\n".join(lines))


def flip_hex(h):
    prefix, hexpart = h.split(":", 1)
    first = "1" if hexpart[0] != "1" else "2"
    return prefix + ":" + first + hexpart[1:]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook call expected")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)


def build(repo, variant):
    repo.mkdir(parents=True, exist_ok=True)
    write_fake_cache_manager(repo)
    write_fixture_file(repo)
    data = allowlist_bytes([valid_entry()])
    seal = seal_of(data)
    if variant == "file_changed_one_byte":
        data = data + b"\n"
    (repo / ".secret-allowlist.json").write_bytes(data)

    if variant in ("sealed", "file_changed_one_byte"):
        write_decision(repo, 1, "ratified", seal)
    elif variant == "decision_hash_changed":
        write_decision(repo, 1, "ratified", flip_hex(seal))
    elif variant == "decision_not_ratified":
        write_decision(repo, 1, "draft", seal)
    elif variant == "no_decision":
        pass
    elif variant == "later_decision_other_hash":
        write_decision(repo, 1, "ratified", seal)
        write_decision(repo, 2, "ratified", flip_hex(seal))
    else:
        raise AssertionError("unknown variant " + variant)


def invalid_matches(matches):
    return [m for m in matches if field(m, "rule_id") == "allowlist-invalid"]


def secret_matches(matches):
    return [
        m
        for m in matches
        if field(m, "rule_id") == RULE and field(m, "file") == FIXTURE_FILE
    ]


def test_sealed_allowlist_allows_finding(tmp_path):
    repo = tmp_path / "repo"
    build(repo, "sealed")

    result = secret_scanner.scan(repo)

    matches = list(field(result, "matches"))
    allowed = list(field(result, "allowed"))
    assert field(result, "flagged") is False, matches
    assert matches == []
    assert any(
        field(a, "rule_id") == RULE
        and field(a, "file") == FIXTURE_FILE
        and field(a, "line") == 1
        for a in allowed
    ), allowed


@pytest.mark.parametrize(
    "variant",
    [
        "file_changed_one_byte",
        "decision_hash_changed",
        "decision_not_ratified",
        "no_decision",
        "later_decision_other_hash",
    ],
)
def test_unsealed_allowlist_fails_closed(tmp_path, variant):
    repo = tmp_path / "repo"
    build(repo, variant)

    result = secret_scanner.scan(repo)

    matches = list(field(result, "matches"))
    allowed = list(field(result, "allowed"))

    assert field(result, "flagged") is True
    found = secret_matches(matches)
    assert len(found) == 1, matches
    assert field(found[0], "line") == 1
    assert field(found[0], "risk_tier") == "high"
    assert not any(
        field(a, "rule_id") == RULE and field(a, "file") == FIXTURE_FILE for a in allowed
    ), allowed

    invalid = invalid_matches(matches)
    assert len(invalid) == 1, matches
    assert field(invalid[0], "risk_tier") == "high"
    assert field(invalid[0], "file") == ".secret-allowlist.json"
    assert field(invalid[0], "line") == 1


def test_empty_allowlist_without_decision_is_not_invalid(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    write_fake_cache_manager(repo)
    write_fixture_file(repo)
    (repo / ".secret-allowlist.json").write_bytes(allowlist_bytes([]))

    result = secret_scanner.scan(repo)

    matches = list(field(result, "matches"))
    assert invalid_matches(matches) == [], matches
    assert len(secret_matches(matches)) == 1, matches