# hotdocs-criterion: sha256:3d41298a02339c1f6da36f71a4d0866f39bdef49428e535c5a4c8d6a473cff79
"""AC-PROVCHECK-001 (covers R-PROVCHECK-002).

Given gen/foo/.provenance.json exists with spec_bundle_hash H, and its
verification_report has no llm-judge-kind criteria, when check_provenance
is called for comp-foo with spec_bundle_hash H, then the result's hit is
true and verification_report, license_scan and secret_scan match the
committed manifest exactly.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
H = "sha256:" + "0123456789abcdef" * 4


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    src = (
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
    path.write_text(src, encoding="utf-8")
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
        "A fixture component.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _build_manifest(python_asset):
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
                    "model": "claude-sonnet-5",
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
        "assets": [copy.deepcopy(python_asset)],
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
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "spec_bundle_hash": H,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "generation": {
            "mode": "single",
            "generator_version": "generator@3.0.0+v11",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "attempts": 1,
        "attempt_history": [],
        "pipeline_version": "v1",
        "gate_versions": {},
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-001",
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
        "assets": [copy.deepcopy(python_asset)],
    }


@pytest.mark.parametrize("trust_judge", [None, "false", "true"])
def test_hash_match_without_llm_judge_is_hit_with_verbatim_results(tmp_path, monkeypatch, trust_judge):
    # The variable only governs llm-judge criteria: with none present, a
    # hash match is a hit however VAR-TRUST-JUDGE-PROVENANCE resolves.
    if trust_judge is None:
        monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    else:
        monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", trust_judge)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_path = _write_python_adapter(repo_root)
    _write_component_md(repo_root)

    python_asset = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha256_of(adapter_path),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = _build_manifest(python_asset)

    # Sanity: the precondition really has no llm-judge-kind criteria.
    assert all(c["kind"] != "llm-judge" for c in manifest["verification_report"]["criteria"])

    manifest_dir = repo_root / "gen" / "foo"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / ".provenance.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    committed = json.loads((manifest_dir / ".provenance.json").read_text(encoding="utf-8"))

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is True, "expected a hit, got reason " + repr(field(result, "reason"))
    assert field(result, "reason") is None
    assert field(result, "verification_report") == committed["verification_report"]
    assert field(result, "license_scan") == committed["license_scan"]
    assert field(result, "secret_scan") == committed["secret_scan"]