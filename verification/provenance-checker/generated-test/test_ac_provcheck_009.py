import json
import os
from pathlib import Path

import pytest

import provenance_checker


LOG_ENV = "PROVCHECK_AC009_LOG_DIR"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ASSEMBLER_SRC = '''import json
import os
from dataclasses import dataclass, field
from pathlib import Path

RAISE = __RAISE__


@dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__.keys())


@dataclass
class CriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def _log(record):
    log_dir = os.environ.get("PROVCHECK_AC009_LOG_DIR")
    if not log_dir:
        return
    with open(Path(log_dir) / "assemble.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def assemble(component_id, repo_root=None, mode="cold"):
    _log({"component_id": component_id, "repo_root": str(repo_root), "mode": mode})
    if RAISE:
        raise ValueError("fake-assemble-refused-ac009")
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:abc",
        spec="",
        interface="",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root=None):
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="",
        criterion_text="",
        requirement_text="",
        interface="",
        glossary="",
        dependency_interfaces={},
    )
'''


COMPILER_SRC = '''GATE_VERSION = "cc@1"


def compile(component_id, repo_root, target="pytest", out_dir=None):
    raise AssertionError("compile must not be called")


def compile_criterion(criterion, surface=None):
    return {"status": "error", "message": "line 1: not used"}
'''


TEST_AUTHOR_SRC = '''GATE_VERSION = "ta@1"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    raise AssertionError("author_test must not be called")
'''


VERIFIER_SRC = '''GATE_VERSION = "vo@1"


def verify(component_id, repo_root, judge=None, test_author=None):
    raise AssertionError("verify must not be called")
'''


LICENSE_SRC = '''import json
import os
from pathlib import Path


def _log(record):
    log_dir = os.environ.get("PROVCHECK_AC009_LOG_DIR")
    if not log_dir:
        return
    with open(Path(log_dir) / "license_scan.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def gate_version(repo_root):
    return "ls@1"


def scan(component_id, repo_root):
    _log({"component_id": component_id, "repo_root": str(repo_root)})
    return {
        "component_id": component_id,
        "gate_version": "ls@1",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''


SECRET_SRC = '''import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


class AllowlistInvalidError(Exception):
    pass


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list = field(default_factory=list)
    allowed: list = field(default_factory=list)
    unused_allowlist_entries: list = field(default_factory=list)
    notified: bool = False
    notification_delivery_error: object = None
    cache_hit: bool = False

    def to_dict(self):
        return asdict(self)


def _log(record):
    log_dir = os.environ.get("PROVCHECK_AC009_LOG_DIR")
    if not log_dir:
        return
    with open(Path(log_dir) / "secret_scan.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def gate_version(repo_root):
    return "ss@1"


def scan(repo_root):
    _log({"fn": "scan", "repo_root": str(repo_root)})
    return SecretScanResult(scope="full", gate_version="ss@1", flagged=False)


def scan_files(paths, repo_root=None):
    _log({"fn": "scan_files", "repo_root": str(repo_root)})
    return SecretScanResult(scope="precommit", gate_version="ss@1", flagged=False)


def propose(repo_root):
    _log({"fn": "propose", "repo_root": str(repo_root)})
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


CRITERION_COMPILER_COMPONENT_MD = """---
id: comp-criterion-compiler
title: Criterion Compiler
status: draft
owners: [pipeline-team]
sealed: true
source_path: pipeline/criterion-compiler/
depends_on: []
---

# Criterion Compiler

## Purpose

Compiles criteria.
"""


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root, assemble_raises):
    assembler = ASSEMBLER_SRC.replace("__RAISE__", "True" if assemble_raises else "False")
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler)
    _write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", COMPILER_SRC)
    _write(repo_root / "gen" / "test-author" / "test_author.py", TEST_AUTHOR_SRC)
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_SRC)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SRC)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SRC)
    _write(
        repo_root / "specs" / "components" / "criterion-compiler" / "component.md",
        CRITERION_COMPILER_COMPONENT_MD,
    )


def _read_log(log_dir, name):
    path = log_dir / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_current_provenance_key_reads_cold_hash_and_gate_versions_without_scanning(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    repo_root.mkdir()
    _build_repo(repo_root, assemble_raises=False)
    monkeypatch.setenv(LOG_ENV, str(log_dir))

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert field(key, "spec_bundle_hash") == "sha256:abc"

    calls = _read_log(log_dir, "assemble.jsonl")
    assert len(calls) >= 1, "faked assemble was never called"
    assert any(
        c["component_id"] == "comp-foo" and c["mode"] == "cold" for c in calls
    ), "assemble was not called for comp-foo with mode 'cold': %r" % (calls,)
    for c in calls:
        assert c["mode"] == "cold"
        assert c["component_id"] == "comp-foo"

    gate_versions = field(key, "gate_versions")
    assert dict(gate_versions) == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
    }

    assert _read_log(log_dir, "license_scan.jsonl") == [], "license-scanner's scan was called"
    assert _read_log(log_dir, "secret_scan.jsonl") == [], "secret-scanner's scan was called"


def test_current_provenance_key_propagates_assemble_value_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    repo_root.mkdir()
    _build_repo(repo_root, assemble_raises=True)
    monkeypatch.setenv(LOG_ENV, str(log_dir))

    with pytest.raises(ValueError, match="fake-assemble-refused-ac009"):
        provenance_checker.current_provenance_key("comp-foo", repo_root)

    calls = _read_log(log_dir, "assemble.jsonl")
    assert len(calls) >= 1, "faked assemble was never called"
    assert _read_log(log_dir, "license_scan.jsonl") == []
    assert _read_log(log_dir, "secret_scan.jsonl") == []