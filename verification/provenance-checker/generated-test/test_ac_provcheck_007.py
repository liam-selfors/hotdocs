# hotdocs-criterion: sha256:23fe7493012aadff0d6a1f8055a599208bdfbebdafb29c63a6e7c1819698eef7
"""AC-PROVCHECK-007: check_provenance compares exactly the caller-supplied
spec_bundle_hash against the manifest's own spec_bundle_hash field, and never
computes a spec_bundle_hash of its own (R-PROVCHECK-001)."""

import hashlib
import json
from pathlib import Path

import provenance_checker


MANIFEST_HASH = "sha256:" + "1" * 64
OTHER_HASH = "sha256:" + "b" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _python_adapter_source():
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    return (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )


def _assembler_source(log_path, returned_hash):
    return (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "class _Bundle:\n"
        "    def __init__(self, **kw):\n"
        "        self.__dict__.update(kw)\n"
        "    def __getitem__(self, key):\n"
        "        return self.__dict__[key]\n"
        "    def get(self, key, default=None):\n"
        "        return self.__dict__.get(key, default)\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log({'call': 'assemble', 'component_id': component_id, 'mode': mode})\n"
        "    return _Bundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash=" + repr(returned_hash) + ",\n"
        "        spec='',\n"
        "        interface='',\n"
        "        constraints='',\n"
        "        dependency_interfaces={},\n"
        "        dependency_context={},\n"
        "        dependency_usage={},\n"
        "        vars={},\n"
        "        glossary='',\n"
        "        hint_code=None,\n"
        "        spec_bundle_parts={'spec': " + repr("sha256:" + "d" * 64)
        + ", 'dependency_code': " + repr("sha256:" + "e" * 64) + "},\n"
        "    )\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log({'call': 'assemble_criterion', 'component_id': component_id})\n"
        "    return _Bundle(\n"
        "        component_id=component_id,\n"
        "        criterion_id=criterion_id,\n"
        "        covers='',\n"
        "        criterion_text='',\n"
        "        requirement_text='',\n"
        "        interface='',\n"
        "        glossary='',\n"
        "        dependency_interfaces={},\n"
        "        testing='',\n"
        "    )\n"
    )


def _build_repo(tmp_path, assembler_hash):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "assemble_calls.log"

    adapter = _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        _python_adapter_source(),
    )
    pa = _sha256_file(adapter)

    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _assembler_source(log_path, assembler_hash),
    )

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
        "# Foo\n",
    )

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = {
        "spec_bundle_hash": MANIFEST_HASH,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
        "drivers": [],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest))
    return repo_root, log_path


def _assemble_calls(log_path):
    if not log_path.exists():
        return []
    return [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_caller_hash_matching_manifest_hits_even_when_bundle_would_differ(tmp_path):
    # The current bundle (as the assembler would compute it) differs from the
    # manifest, but the caller supplies the manifest's hash: a hit, because the
    # comparison uses exactly the caller-supplied value.
    repo_root, log_path = _build_repo(tmp_path, assembler_hash=OTHER_HASH)

    result = provenance_checker.check_provenance(
        "comp-foo", MANIFEST_HASH, {}, repo_root
    )

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert _assemble_calls(log_path) == []


def test_caller_hash_differing_from_manifest_misses_even_when_bundle_would_match(tmp_path):
    # The current bundle (as the assembler would compute it) equals the
    # manifest's hash, but the caller supplies a different one: a miss, because
    # the checker never substitutes a hash of its own.
    repo_root, log_path = _build_repo(tmp_path, assembler_hash=MANIFEST_HASH)

    result = provenance_checker.check_provenance(
        "comp-foo", OTHER_HASH, {}, repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert _assemble_calls(log_path) == []