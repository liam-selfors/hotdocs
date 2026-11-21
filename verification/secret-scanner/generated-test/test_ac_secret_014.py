# hotdocs-criterion: sha256:b84fd923562d8d6a36fd06cca23538f12f4f50f0a8fe65b3ad6f5fb65af1947b
import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


AWS_KEY = "AKIAABCDEFGHIJKLMNOP"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha1_of(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


FAKE_CACHE_MANAGER_SRC = (
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
)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def build_repo(root, files, entries):
    write(root, "gen/cache-manager/cache_manager.py", FAKE_CACHE_MANAGER_SRC)
    for rel, text in files.items():
        write(root, rel, text)
    allowlist = {"version": 1, "entries": entries}
    data = (json.dumps(allowlist, indent=2) + "\n").encode("utf-8")
    (root / ".secret-allowlist.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    decision = (
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
        "Seals the secret allowlist.\n"
    )
    write(root, "specs/decisions/D1.md", decision)


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("urlopen must not be called")


@pytest.fixture
def recorder(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", rec)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", rec)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    return rec


def first_scenario_repo(root):
    build_repo(
        root,
        {"verification/foo/test_x.py": "K = " + repr(AWS_KEY) + "\n"},
        [
            {
                "file": "verification/foo/test_x.py",
                "type": "AWS Access Key",
                "hashed_secret": sha1_of(AWS_KEY),
                "reason": "planted-fixture",
            }
        ],
    )


def has_entry(items, expected):
    for item in items:
        if all(field(item, k) == v for k, v in expected.items()):
            return True
    return False


def test_planted_fixture_suppressed_and_no_notification(tmp_path, monkeypatch, recorder):
    root = tmp_path / "repo"
    root.mkdir()
    first_scenario_repo(root)
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:9/hook")
    monkeypatch.chdir(root)

    result = secret_scanner.scan(root)

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []
    allowed = list(field(result, "allowed"))
    assert len(allowed) == 1
    assert field(allowed[0], "rule_id") == "AWS Access Key"
    assert field(allowed[0], "file") == "verification/foo/test_x.py"
    assert field(allowed[0], "line") == 1
    assert field(result, "notified") is False
    assert recorder.calls == []


def test_public_constant_hex_suppressed(tmp_path, monkeypatch, recorder):
    root = tmp_path / "repo"
    root.mkdir()
    build_repo(
        root,
        {"gen/foo/g.py": "EMPTY = " + repr(EMPTY_TREE) + "\n"},
        [
            {
                "file": "gen/foo/g.py",
                "type": "Hex High Entropy String",
                "hashed_secret": sha1_of(EMPTY_TREE),
                "reason": "public-constant",
            }
        ],
    )
    monkeypatch.chdir(root)

    result = secret_scanner.scan(root)

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []
    assert has_entry(
        list(field(result, "allowed")),
        {"rule_id": "Hex High Entropy String", "file": "gen/foo/g.py", "line": 1},
    )


def test_unused_entry_reported_and_never_blocks(tmp_path, monkeypatch, recorder):
    root = tmp_path / "repo"
    root.mkdir()
    build_repo(
        root,
        {"verification/foo/readme.txt": "nothing to see here\n"},
        [
            {
                "file": "verification/foo/old.py",
                "type": "AWS Access Key",
                "hashed_secret": sha1_of(AWS_KEY),
                "reason": "planted-fixture",
            }
        ],
    )
    monkeypatch.chdir(root)

    result = secret_scanner.scan(root)

    assert field(result, "flagged") is False
    assert list(field(result, "allowed")) == []
    assert has_entry(
        list(field(result, "unused_allowlist_entries")),
        {"file": "verification/foo/old.py", "type": "AWS Access Key"},
    )


def test_scan_files_honors_allowlist_only_with_repo_root(tmp_path, monkeypatch, recorder):
    root = tmp_path / "repo"
    root.mkdir()
    first_scenario_repo(root)
    target = root / "verification" / "foo" / "test_x.py"
    monkeypatch.chdir(tmp_path)

    with_root = secret_scanner.scan_files([target], repo_root=root)
    without_root = secret_scanner.scan_files([target])

    assert field(with_root, "flagged") is False
    assert field(without_root, "flagged") is True