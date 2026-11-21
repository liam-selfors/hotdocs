# hotdocs-criterion: sha256:7455282bdcee641c6022f4ec9fb60202aed070b414658ba4534ceada4c00c324
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
MANIFEST_HASH = "sha256:" + "1234abcd" * 8
ASSEMBLER_HASH = "sha256:" + "f" * 64
OTHER_HASH = "sha256:" + "0" * 64


def sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_python_adapter(repo_root):
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "KIND = 'python'\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12.4', 'packages': "
        + repr(PK)
        + "}, 'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
    )
    path.write_text(src)
    return path


def write_assembler_stand_in(repo_root, log_path):
    path = repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class SpecBundle:\n"
        "    def __init__(self, **kw):\n"
        "        self.__dict__.update(kw)\n"
        "\n"
        "    def __getitem__(self, k):\n"
        "        return self.__dict__[k]\n"
        "\n"
        "    def get(self, k, d=None):\n"
        "        return self.__dict__.get(k, d)\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(repr((component_id, str(repo_root), mode)) + '\\n')\n"
        "    return SpecBundle(component_id=component_id, spec_bundle_hash="
        + repr(ASSEMBLER_HASH)
        + ", spec='', interface='', constraints='', dependency_interfaces={},"
        " dependency_context={}, dependency_usage={}, vars={}, glossary='', hint_code=None)\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(repr(('criterion', component_id, criterion_id)) + '\\n')\n"
        "    raise RuntimeError('not expected')\n"
    )
    path.write_text(src)
    return path


def write_component_md(repo_root):
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
    )


def write_manifest(repo_root, assets):
    path = repo_root / "gen" / "foo" / ".provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": MANIFEST_HASH,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
    }
    path.write_text(json.dumps(manifest))
    return manifest


def test_comparison_uses_caller_supplied_hash_and_never_computes_one(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "assemble.log"

    adapter = write_python_adapter(repo_root)
    write_assembler_stand_in(repo_root, log_path)
    write_component_md(repo_root)

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha256_file(adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = write_manifest(repo_root, [p_entry])

    # Caller supplies exactly the manifest's hash: a hit, even though nothing
    # in the working tree would hash to it and the assembler would say otherwise.
    hit = provenance_checker.check_provenance("comp-foo", MANIFEST_HASH, {}, repo_root)
    assert field(hit, "hit") is True
    assert field(hit, "reason") is None
    assert field(hit, "verification_report") == manifest["verification_report"]

    # Caller supplies the hash a self-computation via assemble would yield: a miss,
    # because the comparison is against the manifest's own field only.
    miss_assembler = provenance_checker.check_provenance(
        "comp-foo", ASSEMBLER_HASH, {}, repo_root
    )
    assert field(miss_assembler, "hit") is False
    assert field(miss_assembler, "reason") == "spec_bundle_hash differs"
    assert field(miss_assembler, "verification_report") is None

    # Any other caller-supplied hash: a miss on spec_bundle_hash.
    miss_other = provenance_checker.check_provenance("comp-foo", OTHER_HASH, {}, repo_root)
    assert field(miss_other, "hit") is False
    assert field(miss_other, "reason") == "spec_bundle_hash differs"

    # check_provenance never computed a spec_bundle_hash of its own.
    calls = log_path.read_text().splitlines() if log_path.exists() else []
    assert calls == []