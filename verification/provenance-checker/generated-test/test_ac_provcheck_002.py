# hotdocs-criterion: sha256:d12ea0ddf151d3513294dd01670d2e1f5b323432ef27dab3107873a01c18edde
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
H = "sha256:" + "1" * 64
OTHER_H = "sha256:" + "2" * 64


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _plant_python_adapter(repo_root):
    versions = {"python": "3.12.4", "packages": PK}
    src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\n"
        "        " + repr("ok") + ": True,\n"
        "        " + repr("reason") + ": " + repr("") + ",\n"
        "        " + repr("versions") + ": " + repr(versions) + ",\n"
        "        " + repr("lockfile_sha256") + ": None,\n"
        "        " + repr("interpreter") + ": " + repr("/fake/python") + ",\n"
        "    }\n"
    )
    return _write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def _plant_component(repo_root):
    text = (
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
    _write(repo_root / "specs" / "components" / "foo" / "component.md", text)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    adapter = _plant_python_adapter(repo_root)
    _plant_component(repo_root)
    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha(adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": {"criteria": [], "overall": "pass"},
        "license_scan": {"component_id": "comp-foo", "blocked": False},
        "secret_scan": {"scope": "full", "flagged": False},
        "assets": [p_entry],
        "drivers": [],
    }
    _write(
        repo_root / "gen" / "foo" / ".provenance.json",
        json.dumps(manifest, indent=2),
    )
    return repo_root


def test_different_spec_bundle_hash_is_definitive_miss(tmp_path):
    repo_root = _build_repo(tmp_path)

    result = provenance_checker.check_provenance("comp-foo", OTHER_H, {}, repo_root)

    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


def test_manifest_with_matching_hash_unchanged_by_miss_check(tmp_path):
    # The miss must not be caused by an absent/unreadable manifest: the
    # manifest is still present and still records H after the check.
    repo_root = _build_repo(tmp_path)
    manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
    before = manifest_path.read_bytes()

    result = provenance_checker.check_provenance("comp-foo", OTHER_H, {}, repo_root)

    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert manifest_path.read_bytes() == before
    assert json.loads(before.decode("utf-8"))["spec_bundle_hash"] == H