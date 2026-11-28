# hotdocs-criterion: sha256:294bb9fc8a1b2cef7e4bdc411e52120b9260c446ddc9308b2728b93c15bdfbf2
import hashlib
import json
from pathlib import Path

import provenance_checker


H = "sha256:" + "b" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def python_adapter_source():
    return (
        "KIND = 'python'\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12.4', 'packages': "
        + repr(PK)
        + "}, 'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
    )


def fake_kind_source():
    return (
        "KIND = 'fake'\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': 'G.', 'test_author': 'T.'}\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '', 'versions': {'fakec': '2.0.0'}, 'lockfile_sha256': None}\n"
    )


def fake_driver_source():
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "NAME = 'fake'\n"
        "FIXTURE = 'fake_session'\n"
        "\n"
        "def provision(repo_root):\n"
        "    data = json.loads((Path(repo_root) / 'fakedrv.json').read_text())\n"
        "    return {'ok': True, 'reason': '', 'versions': data['versions'], 'lockfile_sha256': None}\n"
    )


def assembler_source():
    parts = {"spec": "sha256:" + "c" * 64, "dependency_code": "sha256:" + "d" * 64}
    return (
        "class SpecBundle:\n"
        "    def __init__(self, component_id):\n"
        "        self.component_id = component_id\n"
        "        self.spec_bundle_hash = " + repr(H) + "\n"
        "        self.spec = ''\n"
        "        self.interface = ''\n"
        "        self.constraints = ''\n"
        "        self.dependency_interfaces = {}\n"
        "        self.dependency_context = {}\n"
        "        self.dependency_usage = {}\n"
        "        self.vars = {}\n"
        "        self.glossary = ''\n"
        "        self.hint_code = None\n"
        "        self.spec_bundle_parts = " + repr(parts) + "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "class CriterionBundle:\n"
        "    def __init__(self, component_id, criterion_id):\n"
        "        self.component_id = component_id\n"
        "        self.criterion_id = criterion_id\n"
        "        self.covers = ''\n"
        "        self.criterion_text = ''\n"
        "        self.requirement_text = ''\n"
        "        self.interface = ''\n"
        "        self.glossary = ''\n"
        "        self.dependency_interfaces = {}\n"
        "        self.testing = ''\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    return SpecBundle(component_id)\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root=None):\n"
        "    return CriterionBundle(component_id, criterion_id)\n"
    )


def license_source():
    result = {
        "component_id": "comp-foo",
        "gate_version": "ls@1",
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
    return (
        "def gate_version(repo_root):\n"
        "    return 'ls@1'\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    return " + repr(result) + "\n"
    )


def secret_source():
    result = {
        "scope": "full",
        "gate_version": "ss@1",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return (
        "def gate_version(repo_root):\n"
        "    return 'ss@1'\n"
        "\n"
        "def scan(repo_root):\n"
        "    return " + repr(result) + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    return " + repr(result) + "\n"
    )


def write_manifest(repo_root, manifest):
    text = json.dumps(manifest, indent=2)
    write(repo_root / "gen" / "foo" / ".provenance.json", text)
    write(repo_root / "verification" / "foo" / ".provenance.json", text)


def build_repo(tmp_path, include_drivers_in_manifest=True):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    py_adapter = write(repo_root / "gen" / "kind-python" / "kind_python.py", python_adapter_source())
    fake_def = write(
        repo_root / "specs" / "architecture" / "asset-kind-fake.md",
        "# Asset kind: fake\n\nA fixed fake kind definition.\n",
    )
    fake_adapter = write(repo_root / "gen" / "kind-fake" / "kind_fake.py", fake_kind_source())
    driver = write(repo_root / "gen" / "driver-fake" / "driver_fake.py", fake_driver_source())
    write(repo_root / "fakedrv.json", json.dumps({"versions": {"fakedrv": "2.0"}}))

    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "assets: [fake:static/a.fake]\n"
        "drivers: [fake]\n"
        "---\n"
        "\n"
        "# Foo\n",
    )

    # Dependency stand-ins (as AC-PROVCHECK-009 plants them).
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_source())
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = " + repr("cc@1") + "\n",
    )
    write(repo_root / "gen" / "test-author" / "test_author.py", "GATE_VERSION = " + repr("ta@1") + "\n")
    write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr("vo@1") + "\n",
    )
    write(repo_root / "gen" / "license-scanner" / "license_scanner.py", license_source())
    write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", secret_source())
    write(
        repo_root / "gen" / "generator" / "generator.py",
        "GATE_VERSION = " + repr("gen@3") + "\nPROMPT_VERSION = " + repr("v11") + "\n",
    )

    P = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha(py_adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    FAKE = {
        "kind": "fake",
        "path": "static/a.fake",
        "definition_sha256": sha(fake_def),
        "adapter_sha256": sha(fake_adapter),
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    E = [P, FAKE]
    DR = {
        "name": "fake",
        "definition_sha256": None,
        "adapter_sha256": sha(driver),
        "versions": {"fakedrv": "2.0"},
        "lockfile_sha256": None,
    }

    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": E,
    }
    if include_drivers_in_manifest:
        manifest["drivers"] = [DR]
    write_manifest(repo_root, manifest)

    return repo_root, E, DR, driver


def test_driver_versions_change_is_environment_differs(tmp_path):
    repo_root, E, DR, driver = build_repo(tmp_path)
    (repo_root / "fakedrv.json").write_text(json.dumps({"versions": {"fakedrv": "2.1"}}))

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is False
    assert field(result, "reason") == "environment differs"


def test_driver_adapter_change_is_drivers_differ(tmp_path):
    repo_root, E, DR, driver = build_repo(tmp_path)
    with open(driver, "a") as fh:
        fh.write("# a changed comment\n")

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is False
    assert field(result, "reason") == "drivers differ"


def test_manifest_without_drivers_is_drivers_differ(tmp_path):
    repo_root, E, DR, driver = build_repo(tmp_path, include_drivers_in_manifest=False)

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)

    assert field(result, "hit") is False
    assert field(result, "reason") == "drivers differ"


def test_nothing_changed_key_has_drivers_and_hits(tmp_path):
    repo_root, E, DR, driver = build_repo(tmp_path)

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)
    assert field(key, "drivers") == [DR]

    result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)
    assert field(result, "hit") is True
    assert field(result, "reason") is None