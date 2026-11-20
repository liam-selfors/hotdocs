# hotdocs-criterion: sha256:684cd967fa1167d601fdbc499b2fbecef682a1d2ad7cdfebf3f7214f5b8d037d
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _python_adapter_source():
    return (
        "KIND = 'python'\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12.4', 'packages': "
        + repr(PK)
        + "}, 'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        return None\n"
        "    return run\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )


def _assembler_source(log_path, raise_error):
    src = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "class SpecBundle:\n"
        "    def __init__(self, component_id):\n"
        "        self.component_id = component_id\n"
        "        self.spec_bundle_hash = 'sha256:abc'\n"
        "        self.spec = ''\n"
        "        self.interface = ''\n"
        "        self.constraints = ''\n"
        "        self.dependency_interfaces = {}\n"
        "        self.dependency_context = {}\n"
        "        self.dependency_usage = {}\n"
        "        self.vars = {}\n"
        "        self.glossary = ''\n"
        "        self.hint_code = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        try:\n"
        "            return getattr(self, key)\n"
        "        except AttributeError:\n"
        "            raise KeyError(key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'component_id': component_id, 'repo_root': str(repo_root), 'mode': mode}) + '\\n')\n"
    )
    if raise_error:
        src += "    raise ValueError('assemble-sentinel-failure')\n"
    else:
        src += "    return SpecBundle(component_id)\n"
    src += (
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'assemble_criterion': criterion_id}) + '\\n')\n"
        "    raise RuntimeError('assemble_criterion must not be called')\n"
    )
    return src


def _license_scanner_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ls@1'\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('license scan ' + str(component_id) + '\\n')\n"
        "    return {'component_id': component_id, 'gate_version': 'ls@1', 'evaluated': False,\n"
        "            'reason': 'no-reference-corpus', 'similarity_score': None, 'block_threshold': None,\n"
        "            'blocked': False, 'matches': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
    )


def _secret_scanner_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _result():\n"
        "    return {'scope': 'full', 'gate_version': 'ss@1', 'flagged': False, 'matches': [],\n"
        "            'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
        "\n"
        "def _record(what):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(what + '\\n')\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ss@1'\n"
        "\n"
        "def scan(repo_root):\n"
        "    _record('secret scan')\n"
        "    return _result()\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _record('secret scan_files')\n"
        "    r = _result()\n"
        "    r['scope'] = 'precommit'\n"
        "    return r\n"
        "\n"
        "def propose(repo_root):\n"
        "    _record('secret propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


def _build_repo(tmp_path, raise_error=False):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    assemble_log = logs / "assemble.log"
    license_log = logs / "license_scan.log"
    secret_log = logs / "secret_scan.log"

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", _python_adapter_source())
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _assembler_source(assemble_log, raise_error),
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = " + repr("cc@1") + "\n",
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = " + repr("ta@1") + "\n",
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr("vo@1") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n",
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        _license_scanner_source(license_log),
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        _secret_scanner_source(secret_log),
    )
    _write(
        repo_root / "gen" / "generator" / "generator.py",
        "GATE_VERSION = " + repr("gen@3") + "\n"
        "PROMPT_VERSION = " + repr("v11") + "\n",
    )
    return repo_root, assemble_log, license_log, secret_log


def _read_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_current_provenance_key_reads_key_stand_ins(tmp_path):
    repo_root, assemble_log, license_log, secret_log = _build_repo(tmp_path)

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert field(key, "spec_bundle_hash") == "sha256:abc"

    calls = [json.loads(line) for line in _read_lines(assemble_log)]
    assert len(calls) >= 1
    for call in calls:
        assert call.get("component_id") == "comp-foo"
        assert call.get("mode") == "cold"

    assert dict(field(key, "gate_versions")) == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
        "generator": "gen@3+v11",
    }

    assert _read_lines(license_log) == []
    assert _read_lines(secret_log) == []


def test_current_provenance_key_propagates_assemble_value_error(tmp_path):
    repo_root, assemble_log, license_log, secret_log = _build_repo(tmp_path, raise_error=True)

    with pytest.raises(ValueError) as excinfo:
        provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert type(excinfo.value) is ValueError
    assert "assemble-sentinel-failure" in str(excinfo.value)
    assert len(_read_lines(assemble_log)) >= 1
    assert _read_lines(license_log) == []
    assert _read_lines(secret_log) == []