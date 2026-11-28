# hotdocs-criterion: sha256:863a44156718752336d9f5ac48789d9263380016fd34cfcaf6cbe2c8404bdc12
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
    guidance_result = {"generator": "", "test_author": ""}
    src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr(guidance_result) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def _plant_component(repo_root):
    src = (
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
    _write(repo_root / "specs" / "components" / "foo" / "component.md", src)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}


@pytest.mark.parametrize(
    "spec_bundle_hash",
    ["sha256:abc", "sha256:" + "0" * 64, "sha256:deadbeef"],
)
@pytest.mark.parametrize("gen_dir_exists", [False, True])
def test_absent_manifest_is_a_miss(tmp_path, spec_bundle_hash, gen_dir_exists):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_python_adapter(repo_root)
    _plant_component(repo_root)
    if gen_dir_exists:
        (repo_root / "gen" / "foo").mkdir(parents=True, exist_ok=True)

    manifest = repo_root / "gen" / "foo" / ".provenance.json"
    assert not manifest.exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is False
    # A miss never carries partial or best-guess results (R-PROVCHECK-003).
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    # The check is read-only: no manifest appears.
    assert not manifest.exists()