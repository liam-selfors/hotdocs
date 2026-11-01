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


def _build_repo(tmp_path: Path, assemble_log: Path, assemble_raises: bool):
    repo_root = tmp_path / "repo"

    if assemble_raises:
        assemble_src = (
            "def assemble(component_id, repo_root=None, mode=\"cold\"):\n"
            "    raise ValueError(\"assemble boom\")\n"
        )
    else:
        assemble_src = (
            "import json\n"
            "\n"
            "_LOG = %r\n"
            "\n"
            "class _Result:\n"
            "    spec_bundle_hash = \"sha256:abc\"\n"
            "\n"
            "def assemble(component_id, repo_root=None, mode=\"cold\"):\n"
            "    with open(_LOG, \"a\") as f:\n"
            "        f.write(json.dumps({\"component_id\": component_id, \"mode\": mode}) + \"\\n\")\n"
            "    return _Result()\n"
        ) % (str(assemble_log),)

    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assemble_src,
    )

    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = \"cc@1\"\n",
    )

    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = \"ta@1\"\n",
    )

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = \"vo@1\"\n",
    )

    license_log = tmp_path / "license_scan_calls.log"
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        (
            "import json\n"
            "\n"
            "_LOG = %r\n"
            "\n"
            "def gate_version(repo_root):\n"
            "    return \"ls@1\"\n"
            "\n"
            "def scan(component_id, repo_root):\n"
            "    with open(_LOG, \"a\") as f:\n"
            "        f.write(json.dumps({\"component_id\": component_id}) + \"\\n\")\n"
            "    return {\"component_id\": component_id, \"gate_version\": \"ls@1\", "
            "\"similarity_score\": 0.0, \"block_threshold\": 0.7, \"blocked\": False, "
            "\"matches\": [], \"notified\": False, \"notification_delivery_error\": None, "
            "\"cache_hit\": False}\n"
        )
        % (str(license_log),),
    )

    secret_log = tmp_path / "secret_scan_calls.log"
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        (
            "import json\n"
            "\n"
            "_LOG = %r\n"
            "\n"
            "def gate_version(repo_root):\n"
            "    return \"ss@1\"\n"
            "\n"
            "def scan(repo_root):\n"
            "    with open(_LOG, \"a\") as f:\n"
            "        f.write(json.dumps({\"called\": True}) + \"\\n\")\n"
            "    return {\"scope\": \"full\", \"gate_version\": \"ss@1\", \"flagged\": False, "
            "\"matches\": [], \"notified\": False, \"notification_delivery_error\": None, "
            "\"cache_hit\": False}\n"
        )
        % (str(secret_log),),
    )

    return repo_root, license_log, secret_log


def test_current_provenance_key_cold_mode_no_scan(tmp_path):
    assemble_log = tmp_path / "assemble_calls.log"
    repo_root, license_log, secret_log = _build_repo(
        tmp_path, assemble_log, assemble_raises=False
    )

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert _get(key, "spec_bundle_hash") == "sha256:abc"

    assert assemble_log.exists()
    calls = [json.loads(line) for line in assemble_log.read_text().splitlines() if line]
    assert len(calls) == 1
    assert calls[0]["component_id"] == "comp-foo"
    assert calls[0]["mode"] == "cold"

    assert _get(key, "gate_versions") == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
    }

    assert not license_log.exists()
    assert not secret_log.exists()


def test_current_provenance_key_propagates_assemble_error(tmp_path):
    assemble_log = tmp_path / "assemble_calls_err.log"
    repo_root, _license_log, _secret_log = _build_repo(
        tmp_path, assemble_log, assemble_raises=True
    )

    with pytest.raises(ValueError):
        provenance_checker.current_provenance_key("comp-foo", repo_root)