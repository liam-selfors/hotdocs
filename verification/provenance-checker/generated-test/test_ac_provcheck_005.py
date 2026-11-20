# hotdocs-criterion: sha256:62b47bbecc380b49fcce96eff510caf62e6e45e00d77fd34dc8ee5f67cc97913
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


H = "sha256:" + "ab" * 32
PK = "sha256:" + "a" * 64


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _build_repo(repo_root):
    # Fake python adapter (D344), deterministic provision.
    adapter_src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr({
            "ok": True,
            "reason": "",
            "versions": {"python": "3.12.4", "packages": PK},
            "lockfile_sha256": None,
            "interpreter": "/fake/python",
        }) + "\n"
    )
    adapter_path = repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(adapter_path, adapter_src)

    # Component frontmatter: not sealed, no assets line.
    component_md = (
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
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)

    pa = _sha256_file(adapter_path)
    p_entry = {
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
        "assets": [p_entry],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))
    return manifest


def test_ac_provcheck_005_llm_judge_trusted_hash_match_is_hit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    # monkeypatch removes the variable again after the test.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "true")

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is True