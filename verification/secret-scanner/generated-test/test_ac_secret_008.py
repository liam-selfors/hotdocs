# hotdocs-criterion: sha256:2c9b6b8eee55fa89acaccdc62ded663901841e6e4e084010c193d3a2351f9d9a
"""AC-SECRET-008: precommit scan_files scopes to given files, applies the
sealed allowlist relative to repo_root, and never touches cache-manager."""

import hashlib
import json
from pathlib import Path

import secret_scanner


LOG_ENV = "SECRET_SCANNER_TEST_CACHE_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_cache_manager_stand_in(repo_root):
    # Recording stand-in matching cache-manager's documented interface.
    # It reads its log path from an environment variable so it embeds no
    # temporary-directory path.
    src = (
        "import os\n"
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
        "\n"
        "LOG_ENV = " + repr(LOG_ENV) + "\n"
        "\n"
        "def _record(name):\n"
        "    path = os.environ.get(LOG_ENV)\n"
        "    if path:\n"
        "        with open(path, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(name + '\\n')\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: Any\n"
        "    stored_at: str\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _record('get')\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _record('put')\n"
        "    return None\n"
        "\n"
        "def now_iso():\n"
        "    _record('now_iso')\n"
        "    return '2026-01-01T00:00:00Z'\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    _record('stats')\n"
        "    return {'entry_count': 0}\n"
    )
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(src, encoding="utf-8")


def _write_sealed_allowlist(repo_root, secret_value):
    hashed = hashlib.sha1(secret_value.encode("utf-8")).hexdigest()
    allowlist = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": "sha1:" + hashed,
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_path.write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(allowlist_path.read_bytes()).hexdigest()

    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    decision = (
        "---\n"
        "id: D900\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [security-team]\n"
        "last_ratified_commit: 0000000\n"
        "allowlist_sha256: sha256:" + digest + "\n"
        "---\n"
        "\n"
        "# D900\n"
        "\n"
        "Seals the secret allowlist.\n"
    )
    (decisions / "D900.md").write_text(decision, encoding="utf-8")


def test_ac_secret_008_precommit_scoped_allowlisted_no_cache(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    log_path = tmp_path / "cache_calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook call expected")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)

    _write_cache_manager_stand_in(repo_root)

    allowed_secret = "AKIA" + "ABCDEFGHIJKLMNOP"
    flagged_secret = "AKIA" + "ZZZZYYYYXXXXWWWW"

    t_py = repo_root / "verification" / "foo" / "t.py"
    t_py.parent.mkdir(parents=True, exist_ok=True)
    t_py.write_text("K = " + json.dumps(allowed_secret) + "\n", encoding="utf-8")

    c_py = repo_root / "src" / "c.py"
    c_py.parent.mkdir(parents=True, exist_ok=True)
    c_py.write_text("C = " + json.dumps(flagged_secret) + "\n", encoding="utf-8")

    _write_sealed_allowlist(repo_root, allowed_secret)

    result = secret_scanner.scan_files([t_py, c_py], repo_root=repo_root)

    assert field(result, "scope") == "precommit"

    matches = field(result, "matches")
    match_files = [field(m, "file") for m in matches]
    assert match_files, "expected src/c.py to be flagged"
    assert set(match_files) == {"src/c.py"}, match_files

    allowed = field(result, "allowed")
    allowed_files = [field(a, "file") for a in allowed]
    assert "verification/foo/t.py" in allowed_files, allowed_files

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == [], calls