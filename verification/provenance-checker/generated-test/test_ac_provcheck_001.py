# hotdocs-criterion: sha256:9649669407c5c4cf66186f5057068485942eb1375770d05941b142a237085db9
import copy
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "1f" * 32
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


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
        "\n"
        "def guidance():\n"
        "    return " + repr(guidance_result) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
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


def _build_manifest(python_entry):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "generated-test",
                "result": "pass",
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": 0,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.87,
        "mutation_error": None,
        "assets": [python_entry],
        "drivers": [],
        "overall": "pass",
    }
    license_scan = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [
            {"rule_id": "AWS Access Key", "file": "verification/foo/test_x.py", "line": 3}
        ],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    return {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
        "assets": [python_entry],
        "drivers": [],
    }


@pytest.mark.parametrize("trust_judge", [None, "false", "true"])
def test_hash_match_without_llm_judge_is_verbatim_hit(tmp_path, monkeypatch, trust_judge):
    if trust_judge is None:
        monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    else:
        monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", trust_judge)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    adapter = _plant_python_adapter(repo_root)
    _plant_component(repo_root)

    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha(adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = _build_manifest(python_entry)
    assert not any(
        c.get("kind") == "llm-judge" for c in manifest["verification_report"]["criteria"]
    )
    _write(
        repo_root / "gen" / "foo" / ".provenance.json",
        json.dumps(manifest, indent=2, sort_keys=True),
    )
    expected = copy.deepcopy(manifest)

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "verification_report") == expected["verification_report"]
    assert field(result, "license_scan") == expected["license_scan"]
    assert field(result, "secret_scan") == expected["secret_scan"]