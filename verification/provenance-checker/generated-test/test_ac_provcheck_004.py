# hotdocs-criterion: sha256:0dea7541b835b35a2b37ab5b7a1ced3a6c7ecf56a1428975f1896efbef751137
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
H = "sha256:" + "0123456789abcdef" * 4


def _write_python_adapter(repo_root):
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
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _write_manifest(repo_root, assets):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
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
            "assets": assets,
            "overall": "pass",
        },
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_llm_judge_criterion_untrusted_is_a_miss(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_path = _write_python_adapter(repo_root)
    _write_component_md(repo_root)

    pa = "sha256:" + hashlib.sha256(adapter_path.read_bytes()).hexdigest()
    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    _write_manifest(repo_root, [p_entry])

    # monkeypatch removes the variable again after the test
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is False