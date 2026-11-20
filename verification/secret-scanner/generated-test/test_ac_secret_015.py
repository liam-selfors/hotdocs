# hotdocs-criterion: sha256:64d0cbb2df214c2e4a201044452ba05071107197817e39b8a5d881fb3b1cd6fc
import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


ORIGINAL_KEY = "AKIAQWERTYUIOPASDFGH"
OTHER_KEY = "AKIAZZZZYYYYXXXXWWWW"
TEST_X = "verification/foo/test_x.py"
OTHER_PY = "verification/foo/other.py"
AWS = "AWS Access Key"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER = (
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
    "class CacheKey:\n"
    "    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,\n"
    "                 gate_version=None, model_pin=None):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_inputs_hash = gate_inputs_hash\n"
    "        self.gate_version = gate_version\n"
    "        self.model_pin = model_pin\n"
    "\n"
    "\n"
    "class CachedResult:\n"
    "    def __init__(self, gate_type=None, payload=None, stored_at=None):\n"
    "        self.gate_type = gate_type\n"
    "        self.payload = payload\n"
    "        self.stored_at = stored_at\n"
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
    "    now = datetime.datetime.now(datetime.timezone.utc)\n"
    "    return now.strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return dict(entry_count=0)\n"
)


def sha1(value):
    return "sha1:" + hashlib.sha1(value.encode("utf-8")).hexdigest()


def write_test_x(repo_root, extra_lines=None, key=ORIGINAL_KEY):
    lines = [
        "# planted fixture",
        "",
        "K = " + repr(key),
    ]
    if extra_lines:
        lines.extend(extra_lines)
    path = repo_root / TEST_X
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def write_allowlist_and_seal(repo_root, entry_type=AWS):
    allowlist = {
        "version": 1,
        "entries": [
            {
                "file": TEST_X,
                "type": entry_type,
                "hashed_secret": sha1(ORIGINAL_KEY),
                "reason": "planted-fixture",
            }
        ],
    }
    data = (json.dumps(allowlist, indent=2) + "\n").encode("utf-8")
    (repo_root / ".secret-allowlist.json").write_bytes(data)
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    (decisions / "D1.md").write_text(
        "---\n"
        + "id: D1\n"
        + "title: Seal the secret allowlist\n"
        + "status: ratified\n"
        + "owners: [security-team]\n"
        + "last_ratified_commit: 0000000\n"
        + "allowlist_sha256: " + digest + "\n"
        + "---\n"
        + "\n"
        + "# D1\n"
        + "\n"
        + "Records the allowlist seal.\n"
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def fake_urlopen(*args, **kwargs):
        raise AssertionError("webhook must not be called")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    root = tmp_path / "repo"
    root.mkdir()
    cm = root / "gen" / "cache-manager"
    cm.mkdir(parents=True)
    (cm / "cache_manager.py").write_text(FAKE_CACHE_MANAGER)
    write_test_x(root)
    write_allowlist_and_seal(root)
    return root


def matches_of(result):
    return list(field(result, "matches"))


def has(items, file, line=None, rule_id=None):
    for item in items:
        if field(item, "file") != file:
            continue
        if line is not None and field(item, "line") != line:
            continue
        if rule_id is not None and field(item, "rule_id") != rule_id:
            continue
        return True
    return False


def no_invalid(result):
    return not any(
        field(m, "rule_id") == "allowlist-invalid" for m in matches_of(result)
    )


def test_changed_line_is_flagged_and_entry_unused(repo_root):
    write_test_x(repo_root, key=OTHER_KEY)
    write_allowlist_and_seal(repo_root)

    result = secret_scanner.scan(repo_root)

    assert field(result, "flagged") is True
    assert no_invalid(result)
    assert has(matches_of(result), TEST_X, 3, AWS)
    assert list(field(result, "allowed")) == []
    unused = list(field(result, "unused_allowlist_entries"))
    assert any(
        field(e, "file") == TEST_X and field(e, "type") == AWS for e in unused
    )


def test_same_key_in_other_file_is_not_suppressed(repo_root):
    other = repo_root / OTHER_PY
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("K = " + repr(ORIGINAL_KEY) + "\n")
    write_allowlist_and_seal(repo_root)

    result = secret_scanner.scan(repo_root)

    matches = matches_of(result)
    assert len(matches) == 1, matches
    assert field(matches[0], "file") == OTHER_PY
    assert field(result, "flagged") is True
    assert has(list(field(result, "allowed")), TEST_X, 3, AWS)


def test_second_line_with_other_key_is_the_only_match(repo_root):
    write_test_x(repo_root, extra_lines=["J = " + repr(OTHER_KEY)])
    write_allowlist_and_seal(repo_root)

    result = secret_scanner.scan(repo_root)

    matches = matches_of(result)
    assert len(matches) == 1, matches
    assert field(matches[0], "file") == TEST_X
    assert field(matches[0], "line") == 4
    assert field(matches[0], "rule_id") == AWS


def test_entry_type_changed_does_not_suppress(repo_root):
    write_allowlist_and_seal(repo_root, entry_type="Hex High Entropy String")

    result = secret_scanner.scan(repo_root)

    assert field(result, "flagged") is True
    assert has(matches_of(result), TEST_X, 3, AWS)