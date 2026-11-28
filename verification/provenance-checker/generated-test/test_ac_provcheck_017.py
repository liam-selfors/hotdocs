# hotdocs-criterion: sha256:5dd574b70f9d81ea6a4944c2fb426a2e5d283784a7ca8129795f494df7f54ea5
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


PK = "sha256:" + "a" * 64


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def plant_stand_ins(repo_root, log_path):
    sba_src = (
        "class SpecBundle:\n"
        "    _FIELDS = ('component_id', 'spec_bundle_hash', 'spec', 'interface', 'constraints',\n"
        "               'dependency_interfaces', 'dependency_context', 'dependency_usage', 'vars',\n"
        "               'glossary', 'hint_code', 'spec_bundle_parts')\n"
        "    def __init__(self, **kw):\n"
        "        for k in self._FIELDS:\n"
        "            setattr(self, k, kw.get(k))\n"
        "    def __getitem__(self, k):\n"
        "        if k not in self._FIELDS:\n"
        "            raise KeyError(k)\n"
        "        return getattr(self, k)\n"
        "    def get(self, k, default=None):\n"
        "        return getattr(self, k) if k in self._FIELDS else default\n"
        "\n"
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write('assemble ' + str(component_id) + ' ' + str(mode) + '\\n')\n"
        "    return SpecBundle(component_id=component_id, spec_bundle_hash='H', spec='',\n"
        "        interface='', constraints='', dependency_interfaces={}, dependency_context={},\n"
        "        dependency_usage={}, vars={}, glossary='', hint_code=None, spec_bundle_parts={})\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    raise RuntimeError('assemble_criterion not expected')\n"
    )
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", sba_src)
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = " + repr("cc@1") + "\n",
    )
    write(repo_root / "gen" / "test-author" / "test_author.py", "GATE_VERSION = " + repr("ta@1") + "\n")
    write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr("vo@1") + "\nDEFAULT_TEST_TIMEOUT = 300.0\n",
    )
    ls_src = (
        "def gate_version(repo_root):\n"
        "    return " + repr("ls@1") + "\n"
        "def scan(component_id, repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write('license scan\\n')\n"
        "    raise RuntimeError('scan not expected')\n"
    )
    write(repo_root / "gen" / "license-scanner" / "license_scanner.py", ls_src)
    ss_src = (
        "def gate_version(repo_root):\n"
        "    return " + repr("ss@1") + "\n"
        "def scan(repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write('secret scan\\n')\n"
        "    raise RuntimeError('scan not expected')\n"
        "def scan_files(paths, repo_root=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write('secret scan_files\\n')\n"
        "    raise RuntimeError('scan_files not expected')\n"
        "def propose(repo_root):\n"
        "    raise RuntimeError('propose not expected')\n"
    )
    write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", ss_src)
    write(
        repo_root / "gen" / "generator" / "generator.py",
        "GATE_VERSION = " + repr("gen@3") + "\nPROMPT_VERSION = " + repr("v11") + "\n",
    )


def build(tmp_path, include_drivers_in_manifest=True):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    py_provision = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    kind_python = write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "KIND = " + repr("python") + "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "def provision(repo_root):\n"
        "    return " + repr(py_provision) + "\n",
    )

    fake_def = write(
        repo_root / "specs" / "architecture" / "asset-kind-fake.md",
        "# Asset kind fake\n\nFixed definition text.\n",
    )
    fake_provision = {"ok": True, "reason": "", "versions": {"fakec": "2.0.0"}, "lockfile_sha256": None}
    kind_fake = write(
        repo_root / "gen" / "kind-fake" / "kind_fake.py",
        "KIND = " + repr("fake") + "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "G.", "test_author": "T."}) + "\n"
        "def provision(repo_root):\n"
        "    return " + repr(fake_provision) + "\n",
    )

    fakedrv_json = repo_root / "fakedrv.json"
    fakedrv_json.write_text(json.dumps({"versions": {"fakedrv": "2.0"}}))
    driver = write(
        repo_root / "gen" / "driver-fake" / "driver_fake.py",
        "import json\n"
        "NAME = " + repr("fake") + "\n"
        "FIXTURE = " + repr("fake_session") + "\n"
        "def provision(repo_root):\n"
        "    with open(" + repr(str(fakedrv_json)) + ") as f:\n"
        "        data = json.load(f)\n"
        "    return {'ok': True, 'reason': '', 'versions': data['versions'], 'lockfile_sha256': None}\n",
    )

    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "assets: [fake:static/a.fake]\n"
        "drivers: [fake]\n"
        "---\n"
        "\n"
        "# Foo\n",
    )

    plant_stand_ins(repo_root, log_path)

    P = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha_file(kind_python),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    E = [
        P,
        {
            "kind": "fake",
            "path": "static/a.fake",
            "definition_sha256": sha_file(fake_def),
            "adapter_sha256": sha_file(kind_fake),
            "versions": {"fakec": "2.0.0"},
            "lockfile_sha256": None,
        },
    ]
    DR = {
        "name": "fake",
        "definition_sha256": None,
        "adapter_sha256": sha_file(driver),
        "versions": {"fakedrv": "2.0"},
        "lockfile_sha256": None,
    }

    manifest = {
        "spec_bundle_hash": "H",
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": E,
    }
    if include_drivers_in_manifest:
        manifest["drivers"] = [DR]
    write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))

    return {"repo_root": repo_root, "fakedrv_json": fakedrv_json, "driver": driver, "E": E, "DR": DR}


def test_driver_versions_change_is_environment_differs(tmp_path):
    fx = build(tmp_path)
    repo_root = fx["repo_root"]

    baseline = provenance_checker.check_provenance("comp-foo", "H", {}, repo_root)
    assert field(baseline, "hit") is True, field(baseline, "reason")

    fx["fakedrv_json"].write_text(json.dumps({"versions": {"fakedrv": "2.1"}}))
    result = provenance_checker.check_provenance("comp-foo", "H", {}, repo_root)
    assert field(result, "hit") is False
    assert field(result, "reason") == "environment differs"


def test_driver_adapter_change_is_drivers_differ(tmp_path):
    fx = build(tmp_path)
    repo_root = fx["repo_root"]

    with open(fx["driver"], "a") as f:
        f.write("# a changed driver adapter\n")
    result = provenance_checker.check_provenance("comp-foo", "H", {}, repo_root)
    assert field(result, "hit") is False
    assert field(result, "reason") == "drivers differ"


def test_manifest_without_drivers_is_drivers_differ(tmp_path):
    fx = build(tmp_path, include_drivers_in_manifest=False)
    repo_root = fx["repo_root"]

    result = provenance_checker.check_provenance("comp-foo", "H", {}, repo_root)
    assert field(result, "hit") is False
    assert field(result, "reason") == "drivers differ"


def test_unchanged_key_drivers_and_hit(tmp_path):
    fx = build(tmp_path)
    repo_root = fx["repo_root"]

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)
    assert list(field(key, "drivers")) == [fx["DR"]]

    result = provenance_checker.check_provenance("comp-foo", "H", {}, repo_root)
    assert field(result, "hit") is True, field(result, "reason")
    assert field(result, "reason") is None