# hotdocs-criterion: sha256:69c6deebfa1256a2d5c0b963f8a018ad5f1615f262cc9058395cf163eec2cf0b
import copy
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
X = "sha256:" + "b" * 64
H = "sha256:" + "c" * 64

PY_DEFAULT_VERSIONS = {"python": "3.12.4", "packages": PK}
FAKE_DEFAULT_VERSIONS = {"fakec": "2.0.0"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def adapter_source(kind, default_versions, ctl_path, guidance, include_interpreter):
    src = "import json\n"
    src += "import os\n"
    src += "\n"
    src += "KIND = " + repr(kind) + "\n"
    src += "_CTL = " + repr(str(ctl_path)) + "\n"
    src += "_DEFAULT_VERSIONS = " + repr(default_versions) + "\n"
    src += "_GUIDANCE = " + repr(guidance) + "\n"
    src += "_INCLUDE_INTERPRETER = " + repr(include_interpreter) + "\n"
    src += "\n"
    src += "\n"
    src += "def guidance():\n"
    src += "    return dict(_GUIDANCE)\n"
    src += "\n"
    src += "\n"
    src += "def provision(repo_root):\n"
    src += "    versions = dict(_DEFAULT_VERSIONS)\n"
    src += "    lockfile = None\n"
    src += "    if os.path.isfile(_CTL):\n"
    src += "        with open(_CTL, encoding='utf-8') as fh:\n"
    src += "            data = json.load(fh)\n"
    src += "        if 'versions' in data:\n"
    src += "            versions = data['versions']\n"
    src += "        if 'lockfile_sha256' in data:\n"
    src += "            lockfile = data['lockfile_sha256']\n"
    src += "    result = {'ok': True, 'reason': '', 'versions': versions, 'lockfile_sha256': lockfile}\n"
    src += "    if _INCLUDE_INTERPRETER:\n"
    src += "        result['interpreter'] = '/fake/python'\n"
    src += "    return result\n"
    src += "\n"
    src += "\n"
    src += "def layout_errors(asset_file):\n"
    src += "    return []\n"
    src += "\n"
    src += "\n"
    src += "def surface(asset_file):\n"
    src += "    return {'names': []}\n"
    src += "\n"
    src += "\n"
    src += "def asset_runner(asset_file):\n"
    src += "    def run(entry, args):\n"
    src += "        return None\n"
    src += "    return run\n"
    src += "\n"
    src += "\n"
    src += "def strength_sites(asset_file):\n"
    src += "    return []\n"
    src += "\n"
    src += "\n"
    src += "def apply_site(asset_file, site):\n"
    src += "    return None\n"
    return src


class Fixture:
    def __init__(self, base):
        self.repo = base / "repo"
        ctl = base / "ctl"
        ctl.mkdir(parents=True)
        self.repo.mkdir(parents=True)
        self.py_ctl = ctl / "python.json"
        self.fake_ctl = ctl / "fake.json"
        self.py_ctl.write_text("{}", encoding="utf-8")
        self.fake_ctl.write_text("{}", encoding="utf-8")

        py_dir = self.repo / "gen" / "kind-python"
        py_dir.mkdir(parents=True)
        self.py_adapter = py_dir / "kind_python.py"
        self.py_adapter.write_text(
            adapter_source(
                "python",
                PY_DEFAULT_VERSIONS,
                self.py_ctl,
                {"generator": "", "test_author": ""},
                True,
            ),
            encoding="utf-8",
        )

        fake_dir = self.repo / "gen" / "kind-fake"
        fake_dir.mkdir(parents=True)
        self.fake_adapter = fake_dir / "kind_fake.py"
        self.fake_adapter.write_text(
            adapter_source(
                "fake",
                FAKE_DEFAULT_VERSIONS,
                self.fake_ctl,
                {"generator": "G.", "test_author": "T."},
                False,
            ),
            encoding="utf-8",
        )

        arch = self.repo / "specs" / "architecture"
        arch.mkdir(parents=True)
        self.definition = arch / "asset-kind-fake.md"
        self.definition.write_text("# Asset kind fake\n\nFixed definition text.\n", encoding="utf-8")

        comp_dir = self.repo / "specs" / "components" / "foo"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(
            "---\n"
            "id: comp-foo\n"
            "title: Foo\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "assets: [fake:static/a.fake]\n"
            "---\n"
            "\n"
            "# Foo\n",
            encoding="utf-8",
        )

        self.PA = sha_of(self.py_adapter)
        self.D = sha_of(self.definition)
        self.A = sha_of(self.fake_adapter)
        self.P = {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": self.PA,
            "versions": {"python": "3.12.4", "packages": PK},
            "lockfile_sha256": None,
        }
        self.F = {
            "kind": "fake",
            "path": "static/a.fake",
            "definition_sha256": self.D,
            "adapter_sha256": self.A,
            "versions": {"fakec": "2.0.0"},
            "lockfile_sha256": None,
        }
        self.E = [copy.deepcopy(self.P), copy.deepcopy(self.F)]

    def write_manifest(self, assets=None, gate_versions=None):
        manifest = {
            "spec_bundle_hash": H,
            "gate_versions": {} if gate_versions is None else gate_versions,
            "verification_report": {"criteria": []},
            "license_scan": {},
            "secret_scan": {},
            "assets": copy.deepcopy(self.E) if assets is None else assets,
            "drivers": [],
        }
        out = self.repo / "gen" / "foo"
        out.mkdir(parents=True, exist_ok=True)
        (out / ".provenance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def set_python(self, data):
        self.py_ctl.write_text(json.dumps(data), encoding="utf-8")

    def set_fake(self, data):
        self.fake_ctl.write_text(json.dumps(data), encoding="utf-8")

    def check(self):
        return provenance_checker.check_provenance("comp-foo", H, {}, self.repo)


def _py_version_only(fx):
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})


def _py_packages_only(fx):
    fx.set_python({"versions": {"python": "3.12.4", "packages": X}})


def _fake_versions_only(fx):
    fx.set_fake({"versions": {"fakec": "2.1.0"}})


def _fake_lockfile_only(fx):
    fx.set_fake({"lockfile_sha256": X})


def _both_change(fx):
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    fx.set_fake({"versions": {"fakec": "2.1.0"}})


@pytest.mark.parametrize(
    "change",
    [_py_version_only, _py_packages_only, _fake_versions_only, _fake_lockfile_only, _both_change],
    ids=["python-version", "python-packages", "fake-versions", "fake-lockfile", "both"],
)
def test_environment_only_change_is_environment_differs(tmp_path, change):
    fx = Fixture(tmp_path)
    fx.write_manifest()
    change(fx)
    result = fx.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "environment differs"


def _assets_definition_changes(fx):
    original = copy.deepcopy(fx.E)
    fx.definition.write_text("# Asset kind fake\n\nChanged definition text.\n", encoding="utf-8")
    return original


def _assets_only_p(fx):
    return [copy.deepcopy(fx.P)]


def _assets_reversed(fx):
    return list(reversed(copy.deepcopy(fx.E)))


def _assets_appended(fx):
    return copy.deepcopy(fx.E) + [copy.deepcopy(fx.E[1])]


def _assets_adapter_x(fx):
    e = copy.deepcopy(fx.E)
    e[1]["adapter_sha256"] = X
    return e


def _assets_no_definition(fx):
    e = copy.deepcopy(fx.E)
    del e[1]["definition_sha256"]
    return e


@pytest.mark.parametrize(
    "make_assets",
    [
        _assets_definition_changes,
        _assets_only_p,
        _assets_reversed,
        _assets_appended,
        _assets_adapter_x,
        _assets_no_definition,
    ],
    ids=["definition-changes", "only-p", "reversed", "appended", "adapter-x", "no-definition-key"],
)
def test_other_difference_with_version_change_keeps_assets_differ(tmp_path, make_assets):
    fx = Fixture(tmp_path)
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    assets = make_assets(fx)
    fx.write_manifest(assets=assets)
    result = fx.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_version_change_with_gate_versions_mismatch_is_gate_versions_differ(tmp_path):
    fx = Fixture(tmp_path)
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    fx.write_manifest(gate_versions={"verifier": "v@0"})
    result = fx.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "gate_versions differ"


def test_versions_set_back_is_hit(tmp_path):
    fx = Fixture(tmp_path)
    fx.write_manifest()
    fx.set_python({"versions": {"python": "3.12.5", "packages": PK}})
    fx.set_fake({"versions": {"fakec": "2.1.0"}, "lockfile_sha256": X})
    first = fx.check()
    assert field(first, "hit") is False
    assert field(first, "reason") == "environment differs"

    fx.set_python({"versions": {"python": "3.12.4", "packages": PK}})
    fx.set_fake({"versions": {"fakec": "2.0.0"}, "lockfile_sha256": None})
    result = fx.check()
    assert field(result, "hit") is True
    assert field(result, "reason") is None