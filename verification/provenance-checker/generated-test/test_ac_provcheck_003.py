# hotdocs-criterion: sha256:2d97f1d08110a6262430591b9ea406b7618d05194c1e103b39edde095c7b4310
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant_python_adapter(repo_root):
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    source = (
        "import json\n"
        "\n"
        "KIND = " + repr("python") + "\n"
        "\n"
        "_PROVISION = json.loads(" + repr(json.dumps(provision_result)) + ")\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("generator") + ": " + repr("") + ", "
        + repr("test_author") + ": " + repr("") + "}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return json.loads(json.dumps(_PROVISION))\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {" + repr("names") + ": []}\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        return None\n"
        "    return run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", source)


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


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}


@pytest.mark.parametrize("make_gen_dir", [False, True])
@pytest.mark.parametrize(
    "spec_bundle_hash",
    ["sha256:abc", "sha256:" + "0" * 64, "sha256:" + "f" * 64],
)
def test_missing_manifest_is_definitive_miss(tmp_path, make_gen_dir, spec_bundle_hash):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_python_adapter(repo_root)
    _plant_component(repo_root)
    if make_gen_dir:
        (repo_root / "gen" / "foo").mkdir(parents=True, exist_ok=True)

    manifest = repo_root / "gen" / "foo" / ".provenance.json"
    assert not manifest.exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "reason") == "no manifest"
    # A definitive miss: no partial or best-guess values.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    # Read-only: the check never creates the manifest.
    assert not manifest.exists()