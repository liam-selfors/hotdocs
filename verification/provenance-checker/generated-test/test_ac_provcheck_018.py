# hotdocs-criterion: sha256:038b2d599bab91d95be64ab6fd82ba8c29a24443278b5caa4f40eef18135e321
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import provenance_checker


H = "sha256:" + "1" * 64
H2 = "sha256:" + "2" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(repo_root, *args):
    cmd = [
        "git",
        "-c", "user.name=t",
        "-c", "user.email=t@example.com",
        "-c", "commit.gpgsign=false",
    ] + list(args)
    subprocess.run(cmd, cwd=str(repo_root), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def python_adapter_source():
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    return (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )


def fake_adapter_source():
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    return (
        "KIND = " + repr("fake") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "G.", "test_author": "T."}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )


def build_repo(repo_root):
    repo_root = Path(repo_root)
    repo_root.mkdir(parents=True, exist_ok=True)

    write(repo_root / "gen" / "kind-python" / "kind_python.py", python_adapter_source())
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", fake_adapter_source())
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md",
          "# Asset kind: fake\n\nA fixed definition text for the fake kind.\n")

    comp_dir = repo_root / "specs" / "components" / "foo"
    write(comp_dir / "component.md",
          "---\n"
          "id: comp-foo\n"
          "title: Foo\n"
          "status: draft\n"
          "owners: [pipeline-team]\n"
          "depends_on: []\n"
          "assets: [fake:static/a.fake]\n"
          "---\n"
          "\n"
          "# Foo\n"
          "\n"
          "## Purpose\n"
          "\n"
          "Foo.\n")
    write(comp_dir / "requirements" / "R-FOO-001.md", "# R-FOO-001\n\nx\n")
    write(comp_dir / "acceptance" / "AC-FOO-001.md",
          "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\nx holds.\n")

    pa = sha_file(repo_root / "gen" / "kind-python" / "kind_python.py")
    d = sha_file(repo_root / "specs" / "architecture" / "asset-kind-fake.md")
    a = sha_file(repo_root / "gen" / "kind-fake" / "kind_fake.py")
    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    fake_entry = {
        "kind": "fake",
        "path": "static/a.fake",
        "definition_sha256": d,
        "adapter_sha256": a,
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    expected_assets = [p_entry, fake_entry]

    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {"verifier": "v@1"},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": expected_assets,
    }
    write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest))

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")
    return repo_root


def reason_of(result):
    return field(result, "reason")


def test_committed_repo_with_unchanged_spec_is_hash_formula_differs(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {"verifier": "v@2"}, repo_root)
    assert field(result, "hit") is False
    assert reason_of(result) == "hash formula differs"


def test_uncommitted_spec_change_keeps_spec_bundle_hash_differs(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    (repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\ny\n", encoding="utf-8")
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {"verifier": "v@2"}, repo_root)
    assert reason_of(result) == "spec_bundle_hash differs"


def test_generator_gate_difference_keeps_spec_bundle_hash_differs(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {"generator": "g@2"}, repo_root)
    assert reason_of(result) == "spec_bundle_hash differs"


def test_modified_manifest_keeps_spec_bundle_hash_differs(tmp_path):
    original = build_repo(tmp_path / "repo")
    copy_root = tmp_path / "copy-modified"
    shutil.copytree(str(original), str(copy_root))
    manifest_path = copy_root / "gen" / "foo" / ".provenance.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Same content, different bytes: the file is modified in the working tree.
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {"verifier": "v@2"}, copy_root)
    assert reason_of(result) == "spec_bundle_hash differs"


def test_not_a_git_repository_keeps_spec_bundle_hash_differs(tmp_path):
    original = build_repo(tmp_path / "repo")
    copy_root = tmp_path / "copy-nogit"
    shutil.copytree(str(original), str(copy_root))
    shutil.rmtree(str(copy_root / ".git"))
    assert not (copy_root / ".git").exists()
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {"verifier": "v@2"}, copy_root)
    assert reason_of(result) == "spec_bundle_hash differs"