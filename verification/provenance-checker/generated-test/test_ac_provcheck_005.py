# hotdocs-criterion: sha256:3b9013a3c76f17527d67a5e72b36191a7683379be6b38d989684344fb9f76c31
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
H = "sha256:" + "0123456789abcdef" * 4


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _plant_python_adapter(repo_root):
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
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def test_ac_provcheck_005_llm_judge_trusted_hit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_path = _plant_python_adapter(repo_root)
    _plant_component(repo_root)

    pa = _sha256_file(adapter_path)
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    verification_report = {
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": "pass",
                "rationale": "looks right",
            }
        ]
    }
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": verification_report,
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
        "drivers": [],
    }
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "true")

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is True, (
        "expected a hit, got reason " + repr(field(result, "reason"))
    )