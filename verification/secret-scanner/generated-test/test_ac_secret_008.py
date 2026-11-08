import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import secret_scanner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def test_ac_secret_008():
    repo_root = Path(tempfile.mkdtemp(prefix="ac_secret_008_repo_"))
    log_dir = Path(tempfile.mkdtemp(prefix="ac_secret_008_log_"))
    log_path = log_dir / "cache_calls.log"
    env_var = "AC_SECRET_008_CACHE_LOG"
    old_env = os.environ.get(env_var)
    os.environ[env_var] = str(log_path)

    try:
        allowlisted_secret = "AKIAABCDEFGHIJKLMNOP"
        flagged_secret = "AKIAZZZZYYYYXXXXWWWW"

        allowlisted_path = repo_root / "verification" / "foo" / "t.py"
        _write(allowlisted_path, 'K = "%s"\n' % allowlisted_secret)

        flagged_path = repo_root / "src" / "c.py"
        _write(flagged_path, 'C = "%s"\n' % flagged_secret)

        hashed_secret = hashlib.sha1(allowlisted_secret.encode("utf-8")).hexdigest()
        allowlist_doc = {
            "version": 1,
            "entries": [
                {
                    "file": "verification/foo/t.py",
                    "type": "AWS Access Key",
                    "hashed_secret": "sha1:" + hashed_secret,
                    "reason": "planted-fixture",
                }
            ],
        }
        allowlist_path = repo_root / ".secret-allowlist.json"
        allowlist_bytes = json.dumps(allowlist_doc, indent=2).encode("utf-8")
        allowlist_path.parent.mkdir(parents=True, exist_ok=True)
        allowlist_path.write_bytes(allowlist_bytes)

        allowlist_sha256 = hashlib.sha256(allowlist_bytes).hexdigest()

        decision_content = (
            "---\n"
            "id: D9001\n"
            "title: Seal allowlist for AC-SECRET-008 test fixture\n"
            "status: ratified\n"
            "owners: [lselfors]\n"
            "last_ratified_commit: 0000000000000000000000000000000000000000\n"
            "allowlist_sha256: sha256:%s\n"
            "---\n\n"
            "Seals the allowlist used by this test fixture.\n" % allowlist_sha256
        )
        _write(repo_root / "specs" / "decisions" / "D9001.md", decision_content)

        cache_manager_module = '''
import os
from dataclasses import dataclass


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
    pass


def _log_path():
    return os.environ["AC_SECRET_008_CACHE_LOG"]


def get(cache_key, *, repo_root=None):
    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write("get\\n")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write("put\\n")
'''
        _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", cache_manager_module)

        result = secret_scanner.scan_files(
            [allowlisted_path, flagged_path], repo_root=repo_root
        )

        scope = _field(result, "scope")
        matches = _field(result, "matches")
        allowed = _field(result, "allowed")

        assert scope == "precommit"

        assert matches is not None
        match_files = [_field(m, "file") for m in matches]
        assert match_files == ["src/c.py"]

        assert allowed is not None
        allowed_files = [_field(a, "file") for a in allowed]
        assert "verification/foo/t.py" in allowed_files

        if log_path.exists():
            recorded = log_path.read_text(encoding="utf-8")
        else:
            recorded = ""
        assert recorded == ""
    finally:
        if old_env is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = old_env
        shutil.rmtree(repo_root, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)