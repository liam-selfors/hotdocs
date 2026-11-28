# hotdocs-criterion: sha256:e2edf9c0190dbfa045949e07d0af0f0a7a7ce11d2d3056cc016865f4a215d3b2
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _logger_source(log_path):
    return (
        "import json as _json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _record(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(_json.dumps(entry) + '\\n')\n"
    )


def _build_repo(tmp_path, raise_in_assemble=False):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    repo_root.mkdir(parents=True, exist_ok=True)

    assemble_log = logs / "assemble.log"
    license_scan_log = logs / "license_scan.log"
    secret_scan_log = logs / "secret_scan.log"
    other_log = logs / "other.log"

    # component.md for comp-foo: not sealed, no assets line, no drivers line
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

    # fake python asset-kind adapter
    pk = "sha256:" + "a" * 64
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "KIND = 'python'\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12.4', 'packages': "
        + repr(pk)
        + "}, 'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "def asset_runner(asset_file):\n"
        "    def _run(entry, args):\n"
        "        return None\n"
        "    return _run\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n",
    )

    # spec-bundle-assembler stand-in
    if raise_in_assemble:
        assemble_body = (
            "    _record({'component_id': component_id, 'repo_root': str(repo_root), 'mode': mode})\n"
            "    raise ValueError('boom-assemble-xyz')\n"
        )
    else:
        assemble_body = (
            "    _record({'component_id': component_id, 'repo_root': str(repo_root), 'mode': mode})\n"
            "    return _Bundle(\n"
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
            "        spec_bundle_parts={'spec': 'sha256:s1', 'dependency_code': 'sha256:d1'},\n"
            "    )\n"
        )
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _logger_source(assemble_log)
        + "class _Bundle:\n"
        "    def __init__(self, **kw):\n"
        "        self.__dict__.update(kw)\n"
        "    def __getitem__(self, key):\n"
        "        return self.__dict__[key]\n"
        "    def get(self, key, default=None):\n"
        "        return self.__dict__.get(key, default)\n"
        "    def keys(self):\n"
        "        return self.__dict__.keys()\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        + assemble_body
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _record({'assemble_criterion': [component_id, criterion_id]})\n"
        "    raise RuntimeError('assemble_criterion must not be called')\n",
    )

    # criterion-compiler stand-in (sealed path)
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        _logger_source(other_log)
        + "GATE_VERSION = 'cc@1'\n"
        "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
        "    _record({'compile': component_id})\n"
        "    raise RuntimeError('compile must not be called')\n"
        "def compile_criterion(criterion, surface=None):\n"
        "    _record({'compile_criterion': True})\n"
        "    return {'status': 'error', 'message': 'not called'}\n",
    )

    # test-author stand-in
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        _logger_source(other_log)
        + "GATE_VERSION = 'ta@1'\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _record({'author_test': True})\n"
        "    raise RuntimeError('author_test must not be called')\n",
    )

    # verifier-orchestrator stand-in
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        _logger_source(other_log)
        + "GATE_VERSION = 'vo@1'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _record({'verify': component_id})\n"
        "    raise RuntimeError('verify must not be called')\n",
    )

    # license-scanner stand-in
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        "import json as _json\n"
        "SCAN_LOG = " + repr(str(license_scan_log)) + "\n"
        "def gate_version(repo_root):\n"
        "    return 'ls@1'\n"
        "def scan(component_id, repo_root):\n"
        "    with open(SCAN_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(_json.dumps({'scan': component_id}) + '\\n')\n"
        "    return {'component_id': component_id, 'gate_version': 'ls@1', 'evaluated': False,\n"
        "            'reason': 'no-reference-corpus', 'similarity_score': None, 'block_threshold': None,\n"
        "            'blocked': False, 'matches': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n",
    )

    # secret-scanner stand-in
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "import json as _json\n"
        "SCAN_LOG = " + repr(str(secret_scan_log)) + "\n"
        "def _rec(entry):\n"
        "    with open(SCAN_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(_json.dumps(entry) + '\\n')\n"
        "def _result(scope):\n"
        "    return {'scope': scope, 'gate_version': 'ss@1', 'flagged': False, 'matches': [],\n"
        "            'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
        "def gate_version(repo_root):\n"
        "    return 'ss@1'\n"
        "def scan(repo_root):\n"
        "    _rec({'scan': str(repo_root)})\n"
        "    return _result('full')\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _rec({'scan_files': [str(p) for p in paths]})\n"
        "    return _result('precommit')\n"
        "def propose(repo_root):\n"
        "    _rec({'propose': str(repo_root)})\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )

    # generator stand-in
    _write(
        repo_root / "gen" / "generator" / "generator.py",
        _logger_source(other_log)
        + "GATE_VERSION = 'gen@3'\n"
        "PROMPT_VERSION = 'v11'\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _record({'generate': True})\n"
        "    raise RuntimeError('generate must not be called')\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _record({'commit_cache': True})\n"
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    return None\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    return []\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    _record({'write_files': component_id})\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    return (None, [])\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    return (None, [])\n",
    )

    return {
        "repo_root": repo_root,
        "assemble_log": assemble_log,
        "license_scan_log": license_scan_log,
        "secret_scan_log": secret_scan_log,
    }


def test_current_provenance_key_uses_cold_bundle_and_gate_versions(tmp_path):
    fx = _build_repo(tmp_path)
    repo_root = fx["repo_root"]

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert field(key, "spec_bundle_hash") == "sha256:abc"

    calls = [json.loads(line) for line in _log_lines(fx["assemble_log"])]
    assert calls, "assemble was never called"
    for call in calls:
        assert call["component_id"] == "comp-foo"
        assert call["mode"] == "cold"

    gate_versions = field(key, "gate_versions")
    assert dict(gate_versions) == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
        "generator": "gen@3+v11",
    }

    assert _log_lines(fx["license_scan_log"]) == []
    assert _log_lines(fx["secret_scan_log"]) == []


def test_current_provenance_key_propagates_assemble_value_error(tmp_path):
    fx = _build_repo(tmp_path, raise_in_assemble=True)
    repo_root = fx["repo_root"]

    with pytest.raises(ValueError, match="boom-assemble-xyz"):
        provenance_checker.current_provenance_key("comp-foo", repo_root)