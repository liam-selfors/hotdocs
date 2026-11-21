# hotdocs-criterion: sha256:a23d01aa6694965fc0ce46519bb2850a71698bd4013435fb27f97a5af7fe5d71
"""AC-PROVCHECK-003: an absent gen/<slug>/.provenance.json is a definitive miss."""

import provenance_checker

import pytest


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plant_fake_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    source = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    (adapter_dir / "kind_python.py").write_text(source, encoding="utf-8")


def _plant_component(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
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
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _gate_versions():
    return {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v11",
    }


@pytest.mark.parametrize(
    "spec_bundle_hash",
    [
        "sha256:abc",
        "sha256:" + "0" * 64,
        "sha256:" + "f" * 64,
        "sha256:deadbeef",
    ],
)
def test_absent_manifest_is_a_miss(tmp_path, spec_bundle_hash):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_fake_python_adapter(repo_root)
    _plant_component(repo_root)
    (repo_root / "gen" / "foo").mkdir(parents=True, exist_ok=True)

    manifest = repo_root / "gen" / "foo" / ".provenance.json"
    assert not manifest.exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, _gate_versions(), repo_root
    )

    assert field(result, "hit") is False
    # A miss is definitive: none of the hit-only fields is partially populated.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert not manifest.exists()


def test_absent_manifest_with_no_gen_directory_is_a_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_fake_python_adapter(repo_root)
    _plant_component(repo_root)

    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", "sha256:abc", _gate_versions(), repo_root
    )

    assert field(result, "hit") is False