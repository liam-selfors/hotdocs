# hotdocs-criterion: sha256:a10b232e3ca85a651b4246bdca24aefa770439b103f540e7b3f9a4b7d2dd2215
import hashlib
import json
from pathlib import Path

import provenance_checker


H_MANIFEST = "sha256:" + "1" * 64
H_OTHER = "sha256:" + "2" * 64
PK = "sha256:" + "a" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@3.0.0",
    "verifier": "verifier-orchestrator@4.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.2.0+v12",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_python_adapter(repo_root):
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "KIND = 'python'\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12.4', 'packages': "
        + repr(PK)
        + "}, 'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
    )
    path.write_text(src)
    return path


def _write_component_md(repo_root):
    path = repo_root / "specs" / "components" / "foo" / "component.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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
        "A fixture component.\n"
    )


def _write_assembler_standin(repo_root, log_path, returned_hash):
    """A stand-in assembler that, if ever called, would report a hash
    different from what the caller supplies, and logs each call."""
    path = repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "@dataclasses.dataclass\n"
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
        "    spec_bundle_parts: dict = dataclasses.field(default_factory=dict)\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('assemble ' + str(component_id) + '\\n')\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash=" + repr(returned_hash) + ",\n"
        "        spec='',\n"
        "        interface='',\n"
        "        constraints='',\n"
        "        spec_bundle_parts={'spec': " + repr(returned_hash) + ", 'dependency_code': " + repr(returned_hash) + "},\n"
        "    )\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('assemble_criterion ' + str(component_id) + '\\n')\n"
        "    raise RuntimeError('not used')\n"
    )
    path.write_text(src)


def _build_repo(tmp_path, standin_hash):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "assemble.log"
    adapter = _write_python_adapter(repo_root)
    _write_component_md(repo_root)
    _write_assembler_standin(repo_root, log_path, standin_hash)

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha256_file(adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = {
        "spec_bundle_hash": H_MANIFEST,
        "gate_versions": dict(GATE_VERSIONS),
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
        "drivers": [],
    }
    mpath = repo_root / "gen" / "foo" / ".provenance.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest))
    return repo_root, log_path


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [l for l in log_path.read_text().splitlines() if l.strip()]


def test_caller_supplied_hash_matching_manifest_is_a_hit(tmp_path):
    # A stand-in assembler would report a different hash; the checker must
    # use only the caller's hash, which equals the manifest's.
    repo_root, log_path = _build_repo(tmp_path, standin_hash=H_OTHER)

    result = provenance_checker.check_provenance(
        "comp-foo", H_MANIFEST, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "verification_report") == {"criteria": []}
    assert field(result, "license_scan") == {}
    assert field(result, "secret_scan") == {}
    assert _log_lines(log_path) == []


def test_caller_supplied_hash_differing_from_manifest_is_a_miss(tmp_path):
    # A stand-in assembler would report exactly the manifest's hash; the
    # checker must still compare the caller's differing hash and miss.
    repo_root, log_path = _build_repo(tmp_path, standin_hash=H_MANIFEST)

    result = provenance_checker.check_provenance(
        "comp-foo", H_OTHER, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "reason") in ("spec_bundle_hash differs", "hash formula differs")
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert _log_lines(log_path) == []