import hashlib
import json
import textwrap
from pathlib import Path

import secret_scanner


# Canonical AWS documentation example key; matches detect-secrets' AWS Access
# Key regex detector without relying on entropy heuristics.
AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(repo_root / "src" / "config.py", f'AWS_KEY = "{AWS_SECRET}"\n')
    _write(
        repo_root
        / "verification"
        / "secret-scanner"
        / "generated-test"
        / "test_fixture.py",
        f'PLANTED_FIXTURE = "{AWS_SECRET}"\n',
    )
    # Present in the repo but never passed via paths: must never be scanned.
    _write(repo_root / "other.py", f'UNRELATED_KEY = "{AWS_SECRET}"\n')

    allowlist = {
        "version": 1,
        "entries": [
            {
                "file": "verification/secret-scanner/generated-test/test_fixture.py",
                "type": "AWS Access Key",
                "hashed_secret": "sha1:" + hashlib.sha1(AWS_SECRET.encode()).hexdigest(),
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_bytes = json.dumps(allowlist, indent=2).encode()
    (repo_root / ".secret-allowlist.json").write_bytes(allowlist_bytes)
    allowlist_sha256 = hashlib.sha256(allowlist_bytes).hexdigest()

    decisions_dir = repo_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True)
    (decisions_dir / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: Seal secret allowlist fixture\n"
        "status: ratified\n"
        "owners: [secret-scanner-team]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        f"allowlist_sha256: sha256:{allowlist_sha256}\n"
        "---\n\n"
        "Seals `.secret-allowlist.json` for AC-SECRET-008's fixture.\n"
    )

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(
        textwrap.dedent(
            """\
            import os


            def _log(event):
                path = os.environ.get("AC_SECRET_008_CACHE_LOG")
                if path:
                    with open(path, "a") as f:
                        f.write(event + "\\n")


            class CacheKey:
                def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                             gate_version=None, model_pin=None):
                    self.spec_bundle_hash = spec_bundle_hash
                    self.gate_inputs_hash = gate_inputs_hash
                    self.gate_version = gate_version
                    self.model_pin = model_pin


            class CachedResult:
                def __init__(self, gate_type=None, payload=None, stored_at=None):
                    self.gate_type = gate_type
                    self.payload = payload
                    self.stored_at = stored_at


            def get(cache_key, repo_root=None):
                _log("get")
                return None


            def put(cache_key, cached_result, repo_root=None):
                _log("put")
            """
        )
    )

    return repo_root


def test_scan_files_precommit_scoped_no_cache_allowlist_when_repo_root_given(
    tmp_path, monkeypatch
):
    cache_log = tmp_path / "cache_calls.log"
    monkeypatch.setenv("AC_SECRET_008_CACHE_LOG", str(cache_log))

    repo_root = _build_repo(tmp_path)

    flagged_path = repo_root / "src" / "config.py"
    fixture_path = (
        repo_root
        / "verification"
        / "secret-scanner"
        / "generated-test"
        / "test_fixture.py"
    )

    result = secret_scanner.scan_files([flagged_path, fixture_path], repo_root=repo_root)

    assert _get(result, "scope") == "precommit"
    assert _get(result, "cache_hit") is False
    assert _get(result, "flagged") is True

    matches = _get(result, "matches")
    assert len(matches) == 1
    match = matches[0]
    assert _get(match, "file") == "src/config.py"
    assert _get(match, "rule_id") == "AWS Access Key"

    allowed = _get(result, "allowed")
    assert len(allowed) == 1
    allowed_entry = allowed[0]
    assert (
        _get(allowed_entry, "file")
        == "verification/secret-scanner/generated-test/test_fixture.py"
    )
    assert _get(allowed_entry, "rule_id") == "AWS Access Key"

    assert _get(result, "unused_allowlist_entries") == []

    all_files = {_get(m, "file") for m in matches} | {_get(a, "file") for a in allowed}
    assert all("other.py" not in f for f in all_files)

    # No cache-manager lookup must ever have been attempted.
    assert not cache_log.exists()

    as_dict = result.to_dict()
    assert as_dict["scope"] == "precommit"
    assert as_dict["matches"] == matches


def test_scan_files_precommit_reports_given_paths_and_skips_allowlist_without_repo_root(
    tmp_path, monkeypatch
):
    cache_log = tmp_path / "cache_calls.log"
    monkeypatch.setenv("AC_SECRET_008_CACHE_LOG", str(cache_log))

    repo_root = _build_repo(tmp_path)

    flagged_path = repo_root / "src" / "config.py"
    fixture_path = (
        repo_root
        / "verification"
        / "secret-scanner"
        / "generated-test"
        / "test_fixture.py"
    )

    result = secret_scanner.scan_files([flagged_path, fixture_path], repo_root=None)

    assert _get(result, "scope") == "precommit"
    assert _get(result, "cache_hit") is False
    assert _get(result, "flagged") is True

    matches = _get(result, "matches")
    assert len(matches) == 2
    reported_files = {_get(m, "file") for m in matches}
    assert reported_files == {str(flagged_path), str(fixture_path)}

    # No allowlist applied at all when repo_root is absent, even though one
    # of the two secrets matches an entry that would otherwise suppress it.
    assert _get(result, "allowed") == []

    assert not cache_log.exists()