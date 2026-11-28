# hotdocs-criterion: sha256:255ea65dbe7ac1b02d904eb450bbce4b80e35be7f0baa8d8ce6d923b2fa8de2e
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root):
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    kind_python_src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", kind_python_src)

    component_md = (
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
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)
    (repo_root / "gen" / "foo").mkdir(parents=True, exist_ok=True)


@pytest.mark.parametrize(
    "spec_bundle_hash",
    [
        "sha256:abc",
        "sha256:" + "0" * 64,
        "sha256:" + "f" * 64,
    ],
)
def test_missing_manifest_is_a_miss(tmp_path, spec_bundle_hash):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    manifest = repo_root / "gen" / "foo" / ".provenance.json"
    assert not manifest.exists()

    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v11",
    }

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, gate_versions, repo_root
    )

    assert field(result, "hit") is False
    # A definitive miss carries no partial results (R-PROVCHECK-003).
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert not manifest.exists()