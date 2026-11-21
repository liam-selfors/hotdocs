# hotdocs-criterion: sha256:f35e54751d8d5ae534b992aeee16ac66d4857494846bb707ff608f98ab98cb63
import hashlib
import json
import os
from pathlib import Path

import secret_scanner


LOG_ENV = "SECRET_SCANNER_AC008_CM_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return data


def _cache_manager_stand_in_source():
    return (
        "import os\n"
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "def _record(name):\n"
        "    log = os.environ.get(" + repr(LOG_ENV) + ")\n"
        "    if log:\n"
        "        with open(log, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(name + '\\n')\n"
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
        "        return hash('Miss')\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "    def __post_init__(self):\n"
        "        _record('CacheKey')\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "    def __post_init__(self):\n"
        "        _record('CachedResult')\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _record('get')\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _record('put')\n"
        "    return None\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    _record('now_iso')\n"
        "    return '2026-01-01T00:00:00Z'\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    _record('stats')\n"
        "    return {'entry_count': 0}\n"
    )


def test_ac_secret_008_precommit_scan_files(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    log_path = tmp_path / "cache_manager_calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    # Recording cache-manager stand-in, flat-module shape.
    _write(
        repo_root / "gen" / "cache-manager" / "cache_manager.py",
        _cache_manager_stand_in_source(),
    )

    allowed_secret = "AKIAABCDEFGHIJKLMNOP"
    flagged_secret = "AKIAZZZZYYYYXXXXWWWW"

    t_py = repo_root / "verification" / "foo" / "t.py"
    _write(t_py, "K = " + json.dumps(allowed_secret) + "\n")

    c_py = repo_root / "src" / "c.py"
    _write(c_py, "C = " + json.dumps(flagged_secret) + "\n")

    # Allowlist the planted fixture in verification/foo/t.py.
    allowlist = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": "sha1:"
                + hashlib.sha1(allowed_secret.encode("utf-8")).hexdigest(),
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_bytes = _write(
        repo_root / ".secret-allowlist.json",
        json.dumps(allowlist, indent=2) + "\n",
    )
    seal = "sha256:" + hashlib.sha256(allowlist_bytes).hexdigest()

    # Seal it with a decision whose frontmatter carries allowlist_sha256.
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [security-team]\n"
        "last_ratified_commit: 0000000\n"
        "allowlist_sha256: " + seal + "\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "The secret allowlist is reviewed and sealed.\n",
    )

    result = secret_scanner.scan_files([t_py, c_py], repo_root=repo_root)

    assert field(result, "scope") == "precommit"

    matches = field(result, "matches")
    match_files = [field(m, "file") for m in matches]
    assert match_files, "expected src/c.py to be flagged"
    assert set(match_files) == {"src/c.py"}, match_files

    allowed = field(result, "allowed")
    allowed_files = [field(a, "file") for a in allowed]
    assert "verification/foo/t.py" in allowed_files, allowed_files

    calls = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert calls.strip() == "", "cache-manager stand-in was called: " + repr(calls)