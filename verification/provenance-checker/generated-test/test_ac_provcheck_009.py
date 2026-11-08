import json
from pathlib import Path

import pytest

import provenance_checker


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_dependencies(repo_root: Path, assemble_raises: bool) -> None:
    if assemble_raises:
        assemble_body = (
            "def assemble(component_id, repo_root, mode='cold'):\n"
            "    raise ValueError('assemble boom')\n"
        )
    else:
        assemble_body = (
            "import json\n"
            "import os\n"
            "\n"
            "def assemble(component_id, repo_root, mode='cold'):\n"
            "    log_dir = os.environ['PROV_TEST_LOG_DIR']\n"
            "    with open(os.path.join(log_dir, 'assemble_calls.jsonl'), 'a') as f:\n"
            "        f.write(json.dumps({'component_id': component_id, 'mode': mode}) + '\\n')\n"
            "    class _Bundle:\n"
            "        spec_bundle_hash = 'sha256:abc'\n"
            "    return _Bundle()\n"
        )
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assemble_body,
    )

    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = 'cc@1'\n",
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = 'ta@1'\n",
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = 'vo@1'\n",
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        "import json\n"
        "import os\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ls@1'\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    log_dir = os.environ['PROV_TEST_LOG_DIR']\n"
        "    with open(os.path.join(log_dir, 'license_scan_calls.jsonl'), 'a') as f:\n"
        "        f.write(json.dumps({'component_id': component_id}) + '\\n')\n"
        "    return None\n",
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "import json\n"
        "import os\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ss@1'\n"
        "\n"
        "def scan(repo_root):\n"
        "    log_dir = os.environ['PROV_TEST_LOG_DIR']\n"
        "    with open(os.path.join(log_dir, 'secret_scan_calls.jsonl'), 'a') as f:\n"
        "        f.write(json.dumps({'scanned': True}) + '\\n')\n"
        "    return None\n",
    )


def test_current_provenance_key_happy_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("PROV_TEST_LOG_DIR", str(log_dir))

    _setup_dependencies(repo_root, assemble_raises=False)

    result = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert _get(result, "spec_bundle_hash") == "sha256:abc"

    gate_versions = _get(result, "gate_versions")
    assert gate_versions == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
    }

    assemble_log = log_dir / "assemble_calls.jsonl"
    assert assemble_log.exists()
    calls = [json.loads(line) for line in assemble_log.read_text().splitlines() if line]
    assert len(calls) == 1
    assert calls[0]["component_id"] == "comp-foo"
    assert calls[0]["mode"] == "cold"

    assert not (log_dir / "license_scan_calls.jsonl").exists()
    assert not (log_dir / "secret_scan_calls.jsonl").exists()


def test_current_provenance_key_propagates_assemble_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("PROV_TEST_LOG_DIR", str(log_dir))

    _setup_dependencies(repo_root, assemble_raises=True)

    with pytest.raises(ValueError):
        provenance_checker.current_provenance_key("comp-foo", repo_root)