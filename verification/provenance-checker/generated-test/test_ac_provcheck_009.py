# hotdocs-criterion: sha256:7e749210ad6a168e2108d889b4fdec136d9b842aec1d4cfee6775cd233f0db02
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assembler_source(log_path, raise_error):
    src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "class SpecBundle:\n"
        "    _FIELDS = ('component_id', 'spec_bundle_hash', 'spec', 'interface',\n"
        "               'constraints', 'dependency_interfaces', 'dependency_context',\n"
        "               'dependency_usage', 'vars', 'glossary', 'hint_code')\n"
        "    def __init__(self, **kw):\n"
        "        self._values = dict(kw)\n"
        "        for k, v in kw.items():\n"
        "            setattr(self, k, v)\n"
        "    def __getitem__(self, key):\n"
        "        return self._values[key]\n"
        "    def get(self, key, default=None):\n"
        "        return self._values.get(key, default)\n"
        "    def keys(self):\n"
        "        return list(self._FIELDS)\n"
        "    def __iter__(self):\n"
        "        return iter(self._FIELDS)\n"
        "    def __len__(self):\n"
        "        return len(self._FIELDS)\n"
        "\n"
        "def _record(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _record({'component_id': component_id, 'repo_root': str(repo_root), 'mode': mode})\n"
    )
    if raise_error:
        src += "    raise ValueError('assemble stand-in failure')\n"
    else:
        src += (
            "    return SpecBundle(\n"
            "        component_id=component_id,\n"
            "        spec_bundle_hash='sha256:abc',\n"
            "        spec='',\n"
            "        interface='',\n"
            "        constraints='',\n"
            "        dependency_interfaces={},\n"
            "        dependency_context={},\n"
            "        dependency_usage={},\n"
            "        vars={},\n"
            "        glossary='',\n"
            "        hint_code=None,\n"
            "    )\n"
        )
    src += (
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    raise RuntimeError('assemble_criterion must not be called')\n"
    )
    return src


def license_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ls@1'\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('scan ' + str(component_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'gate_version': 'ls@1',\n"
        "        'evaluated': False,\n"
        "        'reason': 'no-reference-corpus',\n"
        "        'similarity_score': None,\n"
        "        'block_threshold': None,\n"
        "        'blocked': False,\n"
        "        'matches': [],\n"
        "        'notified': False,\n"
        "        'notification_delivery_error': None,\n"
        "        'cache_hit': False,\n"
        "    }\n"
    )


def secret_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "class SecretScanResult:\n"
        "    def __init__(self, scope):\n"
        "        self.scope = scope\n"
        "        self.gate_version = 'ss@1'\n"
        "        self.flagged = False\n"
        "        self.matches = []\n"
        "        self.allowed = []\n"
        "        self.unused_allowlist_entries = []\n"
        "        self.notified = False\n"
        "        self.notification_delivery_error = None\n"
        "        self.cache_hit = False\n"
        "    def to_dict(self):\n"
        "        return dict(self.__dict__)\n"
        "\n"
        "def _record(name):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(name + '\\n')\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ss@1'\n"
        "\n"
        "def scan(repo_root):\n"
        "    _record('scan')\n"
        "    return SecretScanResult('full')\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _record('scan_files')\n"
        "    return SecretScanResult('precommit')\n"
        "\n"
        "def propose(repo_root):\n"
        "    _record('propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


PYTHON_ADAPTER = (
    "KIND = 'python'\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': '', 'test_author': ''}\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '',\n"
    "            'versions': {'python': '3.12.4', 'packages': 'sha256:' + 'a' * 64},\n"
    "            'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
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


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
)


def build_repo(tmp_path, raise_error=False):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    assemble_log = logs / "assemble.log"
    license_log = logs / "license_scan.log"
    secret_log = logs / "secret_scan.log"

    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
          assembler_source(assemble_log, raise_error))
    write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
          "GATE_VERSION = " + repr("cc@1") + "\n")
    write(repo_root / "gen" / "test-author" / "test_author.py",
          "GATE_VERSION = " + repr("ta@1") + "\n")
    write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
          "GATE_VERSION = " + repr("vo@1") + "\n")
    write(repo_root / "gen" / "license-scanner" / "license_scanner.py",
          license_source(license_log))
    write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
          secret_source(secret_log))
    write(repo_root / "gen" / "generator" / "generator.py",
          "GATE_VERSION = " + repr("gen@3") + "\n"
          "PROMPT_VERSION = " + repr("v11") + "\n")
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
    write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)

    return repo_root, assemble_log, license_log, secret_log


def read_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_current_provenance_key_reads_stand_ins_without_scanning(tmp_path):
    repo_root, assemble_log, license_log, secret_log = build_repo(tmp_path)

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert field(key, "spec_bundle_hash") == "sha256:abc"

    calls = [json.loads(line) for line in read_lines(assemble_log)]
    assert calls, "assemble was never called"
    assert all(call["component_id"] == "comp-foo" for call in calls)
    assert all(call["mode"] == "cold" for call in calls)

    gate_versions = field(key, "gate_versions")
    assert dict(gate_versions) == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
        "generator": "gen@3+v11",
    }

    assert read_lines(license_log) == []
    assert read_lines(secret_log) == []


def test_current_provenance_key_propagates_assemble_value_error(tmp_path):
    repo_root, assemble_log, license_log, secret_log = build_repo(tmp_path, raise_error=True)

    with pytest.raises(ValueError) as excinfo:
        provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert "assemble stand-in failure" in str(excinfo.value)
    assert read_lines(assemble_log), "assemble was never called"