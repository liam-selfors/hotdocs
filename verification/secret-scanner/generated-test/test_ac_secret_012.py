# hotdocs-criterion: sha256:eeed03a834fcafdfc1a5bbf599ad71208c37a7efd5ef202cdb620c753d4268e1
import hashlib
import json
import os
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCANNER_AC012_CACHE_LOG"
URLOPEN_LOG_ENV = "SECRET_SCANNER_AC012_URLOPEN_LOG"


FAKE_CACHE_MANAGER_SOURCE = '''\
import json
import os
import time
from dataclasses import dataclass
from typing import Any


def _record(name):
    path = os.environ.get("SECRET_SCANNER_AC012_CACHE_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name}) + "\\n")


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str

    def __post_init__(self):
        _record("CacheKey")


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str

    def __post_init__(self):
        _record("CachedResult")


class Miss:
    def __init__(self):
        _record("Miss")

    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    _record("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _record("put")
    return None


def now_iso():
    _record("now_iso")
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stats(*, repo_root=None):
    _record("stats")
    return {"entry_count": 0}


def main(argv=None):
    _record("main")
    return 0
'''


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _planted_secret():
    # Built at runtime so this test file itself carries no literal key.
    return "AKIA" + "IOSFODNN7" + "EXAMPLE"


def _make_repo(base: Path, with_secret: bool) -> Path:
    repo_root = base / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")
    (repo_root / "README.md").write_text("Nothing secret here.\n", encoding="utf-8")
    if with_secret:
        src_dir = repo_root / "gen" / "foo"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "config.py").write_text(
            'AWS_ACCESS_KEY_ID = "' + _planted_secret() + '"\n', encoding="utf-8"
        )
    return repo_root


def _read_log(path: Path):
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _snapshot(root: Path):
    dirs = set()
    files = {}
    for current, dirnames, filenames in os.walk(root):
        cur = Path(current)
        for d in dirnames:
            dirs.add((cur / d).relative_to(root).as_posix())
        for f in filenames:
            p = cur / f
            rel = p.relative_to(root).as_posix()
            st = p.stat()
            files[rel] = (
                st.st_size,
                st.st_mtime_ns,
                hashlib.sha256(p.read_bytes()).hexdigest(),
            )
    return dirs, files


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cache_log = log_dir / "cache_calls.jsonl"
    urlopen_log = log_dir / "urlopen_calls.jsonl"
    monkeypatch.setenv(LOG_ENV, str(cache_log))
    monkeypatch.setenv(URLOPEN_LOG_ENV, str(urlopen_log))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _fake_urlopen(*args, **kwargs):
        with open(os.environ[URLOPEN_LOG_ENV], "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"call": "urlopen"}) + "\n")
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    work = tmp_path / "work"
    work.mkdir()
    return {"base": work, "cache_log": cache_log, "urlopen_log": urlopen_log}


@pytest.mark.parametrize("with_secret", [False, True])
def test_gate_version_matches_scan_result_gate_version(isolated_env, with_secret):
    repo_root = _make_repo(isolated_env["base"], with_secret)

    before = secret_scanner.gate_version(repo_root)
    result = secret_scanner.scan(repo_root)
    after = secret_scanner.gate_version(repo_root)

    scan_gate_version = _field(result, "gate_version")
    assert isinstance(before, str)
    assert before, "gate_version must not be empty"
    assert scan_gate_version == before
    assert after == before

    # Sanity: the stand-in cache-manager is actually what scan wired to,
    # so the "never called" assertion elsewhere is meaningful.
    calls = [rec.get("call") for rec in _read_log(isolated_env["cache_log"])]
    assert "get" in calls, "scan did not consult the stand-in cache-manager: %r" % calls


def test_gate_version_does_not_call_cache_manager_or_write(isolated_env):
    repo_root = _make_repo(isolated_env["base"], with_secret=True)
    cache_log = isolated_env["cache_log"]
    assert not cache_log.exists()

    dirs_before, files_before = _snapshot(repo_root)

    version = secret_scanner.gate_version(repo_root)

    assert isinstance(version, str)
    assert version, "gate_version must not be empty"

    calls = _read_log(cache_log)
    assert calls == [], "gate_version called the cache-manager stand-in: %r" % calls

    dirs_after, files_after = _snapshot(repo_root)
    assert dirs_after == dirs_before, "directories under repo_root changed: added=%r removed=%r" % (
        sorted(dirs_after - dirs_before),
        sorted(dirs_before - dirs_after),
    )
    assert set(files_after) == set(files_before), "files under repo_root added/removed: added=%r removed=%r" % (
        sorted(set(files_after) - set(files_before)),
        sorted(set(files_before) - set(files_after)),
    )
    changed = sorted(k for k in files_before if files_before[k] != files_after[k])
    assert changed == [], "files under repo_root changed: %r" % changed

    assert not isolated_env["urlopen_log"].exists(), "gate_version attempted a network call"