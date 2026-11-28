# hotdocs-criterion: sha256:3792ee8db6a423081b535394d735c960cd426a1113675a067d6156b01fb2f382
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


PK = "sha256:" + "a" * 64


def plant_python_adapter(repo_root):
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


def plant_component(repo_root):
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


def test_ac_provcheck_001_hash_match_without_llm_judge_is_verbatim_hit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Even with judge provenance not trusted, no llm-judge criteria means
    # the hit is honored unconditionally.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")

    adapter_path = plant_python_adapter(repo_root)
    plant_component(repo_root)

    pa = sha256_of(adapter_path)
    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    h = "sha256:" + "0123456789abcdef" * 4

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
                    "seed": 7,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.87,
        "mutation_error": None,
        "assets": [p_entry],
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

    manifest = {
        "spec_bundle_hash": h,
        "gate_versions": {},
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
        "assets": [p_entry],
        "drivers": [],
    }
    manifest_dir = repo_root / "gen" / "foo"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / ".provenance.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    # Reference copies read back from disk, independent of the dicts above.
    committed = json.loads((manifest_dir / ".provenance.json").read_text(encoding="utf-8"))

    result = provenance_checker.check_provenance("comp-foo", h, {}, repo_root)

    assert field(result, "hit") is True, (
        "expected a hit, got reason " + repr(field(result, "reason"))
    )
    assert field(result, "verification_report") == committed["verification_report"]
    assert field(result, "license_scan") == committed["license_scan"]
    assert field(result, "secret_scan") == committed["secret_scan"]