# hotdocs-criterion: sha256:037cf594ff48d6b83ece9120421eff736e0add98a666a8fd4a310ffa1742e667
import hashlib
import json
import os
from pathlib import Path

import provenance_checker


PK = "sha256:" + "a" * 64
H = "sha256:" + "ab" * 32


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _plant_python_adapter(repo_root):
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
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(path, source)
    return path


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
    )
    _write(repo_root / "specs" / "components" / "foo" / "component.md", text)


def _plant_manifest(repo_root, python_entry):
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "llm-judge",
                    "result": "pass",
                    "rationale": "looks right",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": None,
            "mutation_error": None,
            "assets": [python_entry],
            "drivers": [],
            "overall": "pass",
        },
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
        "drivers": [],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest))


def test_ac_provcheck_004_llm_judge_not_trusted_is_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_path = _plant_python_adapter(repo_root)
    _plant_component(repo_root)
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha256_file(adapter_path),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    _plant_manifest(repo_root, python_entry)

    had_prior = "VAR_TRUST_JUDGE_PROVENANCE" in os.environ
    prior = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE")
    os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = "false"
    try:
        result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)
    finally:
        if had_prior:
            os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = prior
        else:
            os.environ.pop("VAR_TRUST_JUDGE_PROVENANCE", None)

    assert field(result, "hit") is False
    # A miss is definitive: no manifest field is passed through partially.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None