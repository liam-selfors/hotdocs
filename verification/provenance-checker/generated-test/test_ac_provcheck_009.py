# hotdocs-criterion: sha256:ac7de7735a6e1094140ff55ce0d054a8638f9a53c459e6e53c70848dc80f9829
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import provenance_checker


LOG_ENV = "PROVCHECK_AC009_LOG"


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_helper_source():
    return (
        "import json\n"
        "import os\n"
        "\n"
        "def _log(kind, payload):\n"
        "    log_path = os.environ.get(" + repr(LOG_ENV) + ")\n"
        "    if not log_path:\n"
        "        return\n"
        "    with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'kind': kind, 'payload': payload}) + '\\n')\n"
        "\n"
    )


def _assembler_source(raise_error):
    src = (
        "import dataclasses\n"
        + _log_helper_source()
        + "@dataclasses.dataclass\n"
        "class SpecBundle:\n"
        "    component_id: str\n"
        "    spec_bundle_hash: str\n"
        "    spec: str\n"
        "    interface: str\n"
        "    constraints: str\n"
        "    dependency_interfaces: dict = dataclasses.field(default_factory=dict)\n"
        "    dependency_context: dict = dataclasses.field(default_factory=dict)\n"
        "    dependency_usage: dict = dataclasses.field(default_factory=dict)\n"
        "    vars: dict = dataclasses.field(default_factory=dict)\n"
        "    glossary: str = ''\n"
        "    hint_code: object = None\n"
        "\n"
        "    def _names(self):\n"
        "        return [f.name for f in dataclasses.fields(self)]\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        if key not in self._names():\n"
        "            raise KeyError(key)\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        if key in self._names():\n"
        "            return getattr(self, key)\n"
        "        return default\n"
        "\n"
        "    def keys(self):\n"
        "        return list(self._names())\n"
        "\n"
        "    def __iter__(self):\n"
        "        return iter(self._names())\n"
        "\n"
        "    def __len__(self):\n"
        "        return len(self._names())\n"
        "\n"
        "    def __contains__(self, key):\n"
        "        return key in self._names()\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', {'component_id': component_id, 'repo_root': str(repo_root), 'mode': mode})\n"
    )
    if raise_error:
        src += "    raise ValueError(" + repr("fake-assemble-failure-ac009") + ")\n"
    else:
        src += (
            "    return SpecBundle(\n"
            "        component_id=component_id,\n"
            "        spec_bundle_hash=" + repr("sha256:abc") + ",\n"
            "        spec='spec',\n"
            "        interface='interface',\n"
            "        constraints='None.',\n"
            "        dependency_interfaces={},\n"
            "        dependency_context={},\n"
            "        dependency_usage={},\n"
            "        vars={},\n"
            "        glossary='glossary',\n"
            "        hint_code=None,\n"
            "    )\n"
        )
    return src


def _constant_source(value):
    return "GATE_VERSION = " + repr(value) + "\n"


def _license_scanner_source():
    return (
        _log_helper_source()
        + "def gate_version(repo_root):\n"
        "    return " + repr("ls@1") + "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', {'component_id': component_id})\n"
        "    raise AssertionError('license scan must not be called')\n"
    )


def _secret_scanner_source():
    return (
        _log_helper_source()
        + "def gate_version(repo_root):\n"
        "    return " + repr("ss@1") + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan', {})\n"
        "    raise AssertionError('secret scan must not be called')\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files', {})\n"
        "    raise AssertionError('secret scan_files must not be called')\n"
    )


def _build_repo(repo_root, raise_error=False):
    gen = repo_root / "gen"
    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _assembler_source(raise_error),
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        _constant_source("cc@1"),
    )
    _write(gen / "test-author" / "test_author.py", _constant_source("ta@1"))
    _write(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        _constant_source("vo@1"),
    )
    _write(gen / "license-scanner" / "license_scanner.py", _license_scanner_source())
    _write(gen / "secret-scanner" / "secret_scanner.py", _secret_scanner_source())
    _write(
        repo_root / "specs" / "components" / "criterion-compiler" / "component.md",
        "---\n"
        "id: comp-criterion-compiler\n"
        "title: Criterion Compiler\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: pipeline/criterion-compiler/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Criterion Compiler\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Compiles criteria.\n",
    )


def _read_log(log_path):
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def test_current_provenance_key_reads_bundle_hash_and_gate_versions(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert field(key, "spec_bundle_hash") == "sha256:abc"

    entries = _read_log(log_path)
    assemble_calls = [e["payload"] for e in entries if e["kind"] == "assemble"]
    assert len(assemble_calls) >= 1
    assert all(c["component_id"] == "comp-foo" for c in assemble_calls)
    assert all(c["mode"] == "cold" for c in assemble_calls)

    gate_versions = field(key, "gate_versions")
    assert dict(gate_versions) == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
    }

    scan_kinds = {"license_scan", "secret_scan", "secret_scan_files"}
    assert [e for e in entries if e["kind"] in scan_kinds] == []


def test_current_provenance_key_propagates_assemble_value_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, raise_error=True)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    with pytest.raises(ValueError, match="fake-assemble-failure-ac009"):
        provenance_checker.current_provenance_key("comp-foo", repo_root)