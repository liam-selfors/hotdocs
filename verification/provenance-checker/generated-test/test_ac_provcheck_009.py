import json
from pathlib import Path

import pytest

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_repo(repo_root: Path) -> None:
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        '''
import os
import json


class _Bundle:
    def __init__(self, spec_bundle_hash):
        self.spec_bundle_hash = spec_bundle_hash


def assemble(component_id, repo_root=None, mode="cold"):
    calls_file = os.environ["PROVTEST_CALLS_FILE"]
    with open(calls_file, "a") as f:
        f.write(json.dumps({
            "fn": "assemble",
            "component_id": component_id,
            "repo_root": str(repo_root),
            "mode": mode,
        }) + "\\n")
    if os.environ.get("PROVTEST_ASSEMBLE_RAISES") == "1":
        raise ValueError("assemble boom")
    return _Bundle("sha256:abc")
''',
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        'GATE_VERSION = "cc@1"\n',
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        'GATE_VERSION = "ta@1"\n',
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        'GATE_VERSION = "vo@1"\n',
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        '''
import os
import json


def gate_version(repo_root):
    return "ls@1"


def scan(component_id, repo_root):
    calls_file = os.environ["PROVTEST_CALLS_FILE"]
    with open(calls_file, "a") as f:
        f.write(json.dumps({"fn": "license_scan", "component_id": component_id}) + "\\n")
    return None
''',
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        '''
import os
import json


def gate_version(repo_root):
    return "ss@1"


def scan(repo_root):
    calls_file = os.environ["PROVTEST_CALLS_FILE"]
    with open(calls_file, "a") as f:
        f.write(json.dumps({"fn": "secret_scan"}) + "\\n")
    return None
''',
    )


def test_current_provenance_key_reads_each_dependency_cold_no_side_effects(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    calls_file = tmp_path / "calls.jsonl"
    monkeypatch.setenv("PROVTEST_CALLS_FILE", str(calls_file))
    monkeypatch.delenv("PROVTEST_ASSEMBLE_RAISES", raising=False)
    _build_repo(repo_root)

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert _get(key, "spec_bundle_hash") == "sha256:abc"
    assert _get(key, "gate_versions") == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
    }

    records = []
    if calls_file.exists():
        for line in calls_file.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))

    assemble_calls = [r for r in records if r["fn"] == "assemble"]
    assert len(assemble_calls) == 1
    assert assemble_calls[0]["component_id"] == "comp-foo"
    assert assemble_calls[0]["mode"] == "cold"

    scan_calls = [r for r in records if r["fn"] in ("license_scan", "secret_scan")]
    assert scan_calls == []


def test_current_provenance_key_propagates_assemble_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    calls_file = tmp_path / "calls.jsonl"
    monkeypatch.setenv("PROVTEST_CALLS_FILE", str(calls_file))
    monkeypatch.setenv("PROVTEST_ASSEMBLE_RAISES", "1")
    _build_repo(repo_root)

    with pytest.raises(ValueError):
        provenance_checker.current_provenance_key("comp-foo", repo_root)