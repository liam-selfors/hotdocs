# hotdocs-criterion: sha256:2e958bba20fc3d2282b4ccea70b4223b2a0ac45bd37eac1ca1a83700abc6a28c
import hashlib
import json
from pathlib import Path

import provenance_checker


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    python_provision = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    python_src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(python_provision) + "\n"
    )
    python_adapter = write(repo_root / "gen" / "kind-python" / "kind_python.py", python_src)

    definition = write(
        repo_root / "specs" / "architecture" / "asset-kind-fake.md",
        "# Asset kind fake\n\nFixed text for the fake kind.\n",
    )

    fake_provision = {
        "ok": True,
        "reason": "",
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    fake_src = (
        "KIND = " + repr("fake") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "G.", "test_author": "T."}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(fake_provision) + "\n"
    )
    fake_adapter = write(repo_root / "gen" / "kind-fake" / "kind_fake.py", fake_src)

    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "assets: [fake:static/a.fake]\n"
        "---\n"
        "\n"
        "# Foo\n",
    )

    P = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha(python_adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    E = [
        P,
        {
            "kind": "fake",
            "path": "static/a.fake",
            "definition_sha256": sha(definition),
            "adapter_sha256": sha(fake_adapter),
            "versions": {"fakec": "2.0.0"},
            "lockfile_sha256": None,
        },
    ]

    manifest = {
        "spec_bundle_hash": "H",
        "gate_versions": {"verifier": "v@1", "compiler": "c@1", "generator": "g@1"},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": E,
        "drivers": [],
    }
    write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))
    return repo_root


def test_non_generator_gate_differences_are_gates_differ(tmp_path):
    repo_root = build_fixture(tmp_path)

    result = provenance_checker.check_provenance(
        "comp-foo",
        "H",
        {"verifier": "v@2", "compiler": "c@1", "generator": "g@1"},
        repo_root,
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "gates differ"

    result = provenance_checker.check_provenance(
        "comp-foo",
        "H",
        {"verifier": "v@2", "compiler": "c@2", "generator": "g@1"},
        repo_root,
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "gates differ"


def test_generator_difference_keeps_gate_versions_differ(tmp_path):
    repo_root = build_fixture(tmp_path)

    result = provenance_checker.check_provenance(
        "comp-foo",
        "H",
        {"verifier": "v@2", "compiler": "c@1", "generator": "g@2"},
        repo_root,
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "gate_versions differ"