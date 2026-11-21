# hotdocs-criterion: sha256:a3c271f1cb7f7853f532140e3f8a53be308861e794f7cdb996d89759ba01cb05
import hashlib
import json
import os
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


H = "sha256:" + "1" * 64
PK = "sha256:" + "a" * 64


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _build_fixture(repo_root):
    # Fake python adapter (D344): deterministic provision.
    adapter_src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
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
    pa = _sha256_file(adapter_path)

    # Component spec: not sealed, no assets line.
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
    )
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": {
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "llm-judge",
                    "result": "pass",
                    "rationale": "looks right",
                }
            ]
        },
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))


def test_llm_judge_criterion_untrusted_is_definitive_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    previous = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE")
    os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = "false"
    try:
        result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)
    finally:
        if previous is None:
            os.environ.pop("VAR_TRUST_JUDGE_PROVENANCE", None)
        else:
            os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = previous

    assert field(result, "hit") is False
    # A miss is definitive: no partial trust of the manifest's fields.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None