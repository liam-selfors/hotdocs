# hotdocs-criterion: sha256:71c6a9dfaf61a61d7f9ef9f0a879c30ef8dd5e863e5014e0a1d5d5fb365e788c
import copy
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
X = "sha256:" + "b" * 64
H = "sha256:" + "c" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _python_adapter_src(state_path):
    return (
        "import json\n"
        "import os\n"
        "\n"
        "KIND = " + repr("python") + "\n"
        "_STATE = " + repr(str(state_path)) + "\n"
        "_PK = " + repr(PK) + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("generator") + ": " + repr("") + ", "
        + repr("test_author") + ": " + repr("") + "}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    versions = {" + repr("python") + ": " + repr("3.12.4") + ", "
        + repr("packages") + ": _PK}\n"
        "    lock = None\n"
        "    if os.path.exists(_STATE):\n"
        "        with open(_STATE, encoding='utf-8') as fh:\n"
        "            data = json.load(fh)\n"
        "        if " + repr("versions") + " in data:\n"
        "            versions = data[" + repr("versions") + "]\n"
        "        if " + repr("lockfile_sha256") + " in data:\n"
        "            lock = data[" + repr("lockfile_sha256") + "]\n"
        "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
        + repr("versions") + ": versions, " + repr("lockfile_sha256") + ": lock, "
        + repr("interpreter") + ": " + repr("/fake/python") + "}\n"
    )


def _fake_adapter_src(state_path):
    return (
        "import json\n"
        "import os\n"
        "\n"
        "KIND = " + repr("fake") + "\n"
        "_STATE = " + repr(str(state_path)) + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("generator") + ": " + repr("G.") + ", "
        + repr("test_author") + ": " + repr("T.") + "}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    versions = {" + repr("fakec") + ": " + repr("2.0.0") + "}\n"
        "    lock = None\n"
        "    if os.path.exists(_STATE):\n"
        "        with open(_STATE, encoding='utf-8') as fh:\n"
        "            data = json.load(fh)\n"
        "        if " + repr("versions") + " in data:\n"
        "            versions = data[" + repr("versions") + "]\n"
        "        if " + repr("lockfile_sha256") + " in data:\n"
        "            lock = data[" + repr("lockfile_sha256") + "]\n"
        "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
        + repr("versions") + ": versions, " + repr("lockfile_sha256") + ": lock}\n"
    )


class Fixture:
    def __init__(self, tmp_path):
        self.repo_root = tmp_path / "repo"
        self.side = tmp_path / "side"
        self.side.mkdir(parents=True)
        self.python_state = self.side / "python_state.json"
        self.fake_state = self.side / "fake_state.json"

        root = self.repo_root
        py_adapter = root / "gen" / "kind-python" / "kind_python.py"
        py_adapter.parent.mkdir(parents=True)
        py_adapter.write_text(_python_adapter_src(self.python_state), encoding="utf-8")

        fake_adapter = root / "gen" / "kind-fake" / "kind_fake.py"
        fake_adapter.parent.mkdir(parents=True)
        fake_adapter.write_text(_fake_adapter_src(self.fake_state), encoding="utf-8")

        self.definition = root / "specs" / "architecture" / "asset-kind-fake.md"
        self.definition.parent.mkdir(parents=True)
        self.definition.write_text("# Asset kind fake\n\nFixed definition text.\n", encoding="utf-8")

        comp = root / "specs" / "components" / "foo" / "component.md"
        comp.parent.mkdir(parents=True)
        comp.write_text(
            "---\n"
            "id: comp-foo\n"
            "title: Foo\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "depends_on: [comp-kind-fake]\n"
            "assets: [fake:static/a.fake]\n"
            "---\n"
            "\n"
            "# Foo\n",
            encoding="utf-8",
        )

        self.manifest_path = root / "gen" / "foo" / ".provenance.json"
        self.manifest_path.parent.mkdir(parents=True)

        pa = _sha(py_adapter)
        d = _sha(self.definition)
        a = _sha(fake_adapter)
        self.P = {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": pa,
            "versions": {"python": "3.12.4", "packages": PK},
            "lockfile_sha256": None,
        }
        self.E = [
            copy.deepcopy(self.P),
            {
                "kind": "fake",
                "path": "static/a.fake",
                "definition_sha256": d,
                "adapter_sha256": a,
                "versions": {"fakec": "2.0.0"},
                "lockfile_sha256": None,
            },
        ]
        self.write_manifest(self.E, {})

    def write_manifest(self, assets, gate_versions):
        manifest = {
            "spec_bundle_hash": H,
            "gate_versions": gate_versions,
            "verification_report": {"criteria": []},
            "license_scan": {},
            "secret_scan": {},
            "assets": assets,
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def set_python(self, data):
        self.python_state.write_text(json.dumps(data), encoding="utf-8")

    def set_fake(self, data):
        self.fake_state.write_text(json.dumps(data), encoding="utf-8")

    def reset_versions(self):
        for p in (self.python_state, self.fake_state):
            if p.exists():
                p.unlink()

    def check(self):
        return provenance_checker.check_provenance("comp-foo", H, {}, self.repo_root)


@pytest.fixture(autouse=True)
def _no_trust_var(monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)


def _python_version_change(fx):
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})


def _python_packages_change(fx):
    fx.set_python({"versions": {"python": "3.12.4", "packages": X}})


def _fake_version_change(fx):
    fx.set_fake({"versions": {"fakec": "2.1.0"}})


def _fake_lockfile_change(fx):
    fx.set_fake({"lockfile_sha256": X})


def _both_change(fx):
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    fx.set_fake({"versions": {"fakec": "2.1.0"}})


@pytest.mark.parametrize(
    "change",
    [
        _python_version_change,
        _python_packages_change,
        _fake_version_change,
        _fake_lockfile_change,
        _both_change,
    ],
    ids=["python-version", "python-packages", "fake-version", "fake-lockfile", "both"],
)
def test_only_versions_or_lockfile_differ_is_environment_differs(tmp_path, change):
    fx = Fixture(tmp_path)
    change(fx)
    result = fx.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "environment differs"


def _definition_changes(fx):
    fx.definition.write_text("# Asset kind fake\n\nA changed definition.\n", encoding="utf-8")


def _manifest_only_python(fx):
    fx.write_manifest([copy.deepcopy(fx.P)], {})


def _manifest_reversed(fx):
    fx.write_manifest(list(reversed(copy.deepcopy(fx.E))), {})


def _manifest_appended(fx):
    e = copy.deepcopy(fx.E)
    e.append(copy.deepcopy(fx.E[1]))
    fx.write_manifest(e, {})


def _manifest_adapter_differs(fx):
    e = copy.deepcopy(fx.E)
    e[1]["adapter_sha256"] = X
    fx.write_manifest(e, {})


def _manifest_lacks_definition(fx):
    e = copy.deepcopy(fx.E)
    del e[1]["definition_sha256"]
    fx.write_manifest(e, {})


@pytest.mark.parametrize(
    "change",
    [
        _definition_changes,
        _manifest_only_python,
        _manifest_reversed,
        _manifest_appended,
        _manifest_adapter_differs,
        _manifest_lacks_definition,
    ],
    ids=[
        "definition-changes",
        "assets-only-P",
        "reversed",
        "appended",
        "adapter-sha-differs",
        "lacks-definition-sha",
    ],
)
def test_other_asset_differences_stay_assets_differ(tmp_path, change):
    fx = Fixture(tmp_path)
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    change(fx)
    result = fx.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_gate_versions_differ_takes_precedence(tmp_path):
    fx = Fixture(tmp_path)
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    fx.write_manifest(fx.E, {"verifier": "v@0"})
    result = fx.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "gate_versions differ"


def test_versions_set_back_hits(tmp_path):
    fx = Fixture(tmp_path)
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    fx.set_fake({"versions": {"fakec": "2.1.0"}, "lockfile_sha256": X})
    changed = fx.check()
    assert field(changed, "hit") is False
    assert field(changed, "reason") == "environment differs"

    fx.reset_versions()
    result = fx.check()
    assert field(result, "hit") is True
    assert field(result, "reason") is None