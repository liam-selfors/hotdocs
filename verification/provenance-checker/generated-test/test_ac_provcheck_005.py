# hotdocs-criterion: sha256:5b43acec8ee7d95f28fe0b52b3e7e3abd0feaf5573fe76481a5d8ff583b81a22
import hashlib
import json
from pathlib import Path

import provenance_checker


PK = "sha256:" + "a" * 64
H = "sha256:" + "0123456789abcdef" * 4


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant_python_adapter(repo_root):
    source = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("generator") + ": " + repr("") + ", "
        + repr("test_author") + ": " + repr("") + "}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\n"
        "        " + repr("ok") + ": True,\n"
        "        " + repr("reason") + ": " + repr("") + ",\n"
        "        " + repr("versions") + ": {" + repr("python") + ": " + repr("3.12.4")
        + ", " + repr("packages") + ": " + repr(PK) + "},\n"
        "        " + repr("lockfile_sha256") + ": None,\n"
        "        " + repr("interpreter") + ": " + repr("/fake/python") + ",\n"
        "    }\n"
    )
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(path, source)
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _plant_component(repo_root):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
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
        "A fixture component.\n",
    )


def test_ac_provcheck_005_llm_judge_hit_when_judge_provenance_trusted(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    pa = _plant_python_adapter(repo_root)
    _plant_component(repo_root)

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    verification_report = {
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
        "assets": [p_entry],
        "drivers": [],
        "overall": "pass",
    }
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": verification_report,
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
        "drivers": [],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest))

    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "true")
    try:
        result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)
    finally:
        monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)

    assert field(result, "hit") is True, (
        "expected a hit, got reason " + repr(field(result, "reason"))
    )