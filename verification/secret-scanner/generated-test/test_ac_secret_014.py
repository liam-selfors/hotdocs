# hotdocs-criterion: sha256:a9cf2ff540b3fd9acfde2ce8e56057eef4672f8cafcecb18a45b63fa984ad0da
"""AC-SECRET-014 (covers R-SECRET-012): exact, sealed allowlist entries
suppress findings, unused entries are reported, and scan_files only
honors the allowlist when given a repo_root."""

import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


AWS_SECRET = "AKIAABCDEFGHIJKLMNOP"
HEX_SECRET = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
AWS_FILE = "verification/foo/test_x.py"
HEX_FILE = "gen/foo/g.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha1_tag(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


FAKE_CACHE_MANAGER_SOURCE = "\n".join([
    "import dataclasses",
    "from datetime import datetime, timezone",
    "",
    "",
    "class SchemaValidationError(ValueError):",
    "    pass",
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
    "@dataclasses.dataclass",
    "class CacheKey:",
    "    spec_bundle_hash: str",
    "    gate_inputs_hash: str",
    "    gate_version: str",
    "    model_pin: str",
    "",
    "",
    "@dataclasses.dataclass",
    "class CachedResult:",
    "    gate_type: str",
    "    payload: dict",
    "    stored_at: str",
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
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')",
    "",
    "",
    "def stats(*, repo_root=None):",
    "    return {'entry_count': 0}",
    "",
])


def write(repo_root, rel, text):
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def install_fake_cache_manager(repo_root):
    write(repo_root, "gen/cache-manager/cache_manager.py", FAKE_CACHE_MANAGER_SOURCE)


def write_sealed_allowlist(repo_root, entries):
    data = {"version": 1, "entries": entries}
    raw = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    (repo_root / ".secret-allowlist.json").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    decision = "\n".join([
        "---",
        "id: D1",
        "title: Seal the secret allowlist",
        "status: ratified",
        "owners: [security-team]",
        "last_ratified_commit: 0000000",
        "allowlist_sha256: sha256:" + digest,
        "---",
        "",
        "# D1",
        "",
        "Seals the current secret allowlist.",
        "",
    ])
    write(repo_root, "specs/decisions/D1.md", decision)


def aws_entry(file_rel=AWS_FILE):
    return {
        "file": file_rel,
        "type": "AWS Access Key",
        "hashed_secret": sha1_tag(AWS_SECRET),
        "reason": "planted-fixture",
    }


def build_aws_repo(repo_root):
    write(repo_root, AWS_FILE, "K = " + repr(AWS_SECRET).replace("'", '"') + "\n")
    write_sealed_allowlist(repo_root, [aws_entry()])


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))

        class _Resp:
            status = 200

            def read(self):
                return b""

            def getcode(self):
                return 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Resp()


@pytest.fixture
def recorder(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", rec)
    monkeypatch.setattr(secret_scanner, "urlopen", rec, raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    return rec


def test_exact_entry_suppresses_aws_key_without_notification(tmp_path, monkeypatch, recorder):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    install_fake_cache_manager(repo_root)
    build_aws_repo(repo_root)
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://example.invalid/hook")

    result = secret_scanner.scan(repo_root)

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []
    allowed = list(field(result, "allowed"))
    assert len(allowed) == 1
    entry = allowed[0]
    assert field(entry, "rule_id") == "AWS Access Key"
    assert field(entry, "file") == AWS_FILE
    assert field(entry, "line") == 1
    assert field(result, "notified") is False
    assert recorder.calls == []


def test_public_constant_entry_suppresses_hex_string(tmp_path, recorder):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    install_fake_cache_manager(repo_root)
    write(repo_root, HEX_FILE, "EMPTY = " + repr(HEX_SECRET).replace("'", '"') + "\n")
    write_sealed_allowlist(repo_root, [{
        "file": HEX_FILE,
        "type": "Hex High Entropy String",
        "hashed_secret": sha1_tag(HEX_SECRET),
        "reason": "public-constant",
    }])

    result = secret_scanner.scan(repo_root)

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []
    allowed = list(field(result, "allowed"))
    assert len(allowed) == 1
    entry = allowed[0]
    assert field(entry, "rule_id") == "Hex High Entropy String"
    assert field(entry, "file") == HEX_FILE
    assert field(entry, "line") == 1


def test_entry_matching_nothing_is_reported_unused(tmp_path, recorder):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    install_fake_cache_manager(repo_root)
    write(repo_root, "verification/foo/old.py", "X = 1\n")
    write_sealed_allowlist(repo_root, [aws_entry("verification/foo/old.py")])

    result = secret_scanner.scan(repo_root)

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []
    assert list(field(result, "allowed")) == []
    unused = list(field(result, "unused_allowlist_entries"))
    assert len(unused) == 1
    assert field(unused[0], "file") == "verification/foo/old.py"
    assert field(unused[0], "type") == "AWS Access Key"


def test_scan_files_honors_allowlist_only_with_repo_root(tmp_path, monkeypatch, recorder):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_aws_repo(repo_root)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    target = repo_root / AWS_FILE

    with_root = secret_scanner.scan_files([target], repo_root=repo_root)
    without_root = secret_scanner.scan_files([target])

    assert field(with_root, "flagged") is False
    assert field(without_root, "flagged") is True