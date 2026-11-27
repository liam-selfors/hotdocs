# hotdocs-criterion: sha256:467cfbec1beb20def7d8aca53b65a2d2d6832b0546898134d0e96c05154bf815
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
H = "sha256:" + "0123456789abcdef" * 4


def _write_fake_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    guidance_result = {"generator": "", "test_author": ""}
    source = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr(guidance_result) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    path = adapter_dir / "kind_python.py"
    path.write_text(source, encoding="utf-8")
    return path


def _write_component_md(repo_root):
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
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _write_manifest(repo_root, python_entry):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-002",
                    "covers": "R-FOO-002",
                    "kind": "llm-judge",
                    "result": "pass",
                    "rationale": "looks right",
                }
            ],
            "requirement_results": {"R-FOO-002": "pass"},
            "overall": "pass",
        },
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
        "drivers": [],
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_ac_provcheck_004_llm_judge_not_trusted_is_miss(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_path = _write_fake_python_adapter(repo_root)
    _write_component_md(repo_root)

    pa = "sha256:" + hashlib.sha256(adapter_path.read_bytes()).hexdigest()
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    _write_manifest(repo_root, python_entry)

    # monkeypatch removes the variable again after the test.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is False
    # A definitive miss: nothing from the manifest is partially trusted.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert field(result, "reason") == "llm-judge results not trusted"