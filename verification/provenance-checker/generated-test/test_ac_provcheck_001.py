# hotdocs-criterion: sha256:309b7b1a08233896d8ac09244b391474eb73a10306204b348d0621cd47234c0e
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


H = "sha256:" + "1f" * 32
PK = "sha256:" + "a" * 64


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    result = {
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
        "    return " + repr(result) + "\n"
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


def _verification_report(python_asset):
    return {
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
        "assets": [python_asset],
        "overall": "pass",
        "extra_marker": {"nested": [1, 2, 3], "note": "kept verbatim"},
    }


LICENSE_SCAN = {
    "component_id": "comp-foo",
    "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
    "evaluated": True,
    "reason": None,
    "similarity_score": 0.12,
    "block_threshold": 0.7,
    "blocked": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": True,
}

SECRET_SCAN = {
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


def _build_fixture(repo_root):
    adapter_path = _write_python_adapter(repo_root)
    _write_component_md(repo_root)
    python_asset = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha256_file(adapter_path),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    report = _verification_report(python_asset)
    manifest = {
        "spec_bundle_hash": H,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v11",
        "retry_feedback": None,
        "attempts": 1,
        "pipeline_version": "v1",
        "gate_versions": {},
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": report,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
        "assets": [python_asset],
    }
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


@pytest.mark.parametrize("trust_value", [None, "false", "true"])
def test_hash_match_without_llm_judge_is_hit_with_verbatim_results(tmp_path, monkeypatch, trust_value):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manifest = _build_fixture(repo_root)

    if trust_value is None:
        monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    else:
        monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", trust_value)

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is True
    assert field(result, "verification_report") == manifest["verification_report"]
    assert field(result, "license_scan") == manifest["license_scan"]
    assert field(result, "secret_scan") == manifest["secret_scan"]