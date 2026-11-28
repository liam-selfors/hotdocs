# hotdocs-criterion: sha256:23dd91f999d369bb34ba833dbe693ec5fa4d3dd29db4347243acd05d8d9b354a
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


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def adapter_source(kind, default_versions, state_path, interpreter):
    lines = [
        "import json",
        "import os",
        "",
        "KIND = " + repr(kind),
        "_STATE = " + repr(str(state_path)),
        "",
        "",
        "def guidance():",
    ]
    if kind == "python":
        lines.append("    return " + repr({"generator": "", "test_author": ""}))
    else:
        lines.append("    return " + repr({"generator": "G.", "test_author": "T."}))
    lines += [
        "",
        "",
        "def provision(repo_root):",
        "    versions = " + repr(default_versions),
        "    lock = None",
        "    if os.path.exists(_STATE):",
        "        with open(_STATE) as fh:",
        "            data = json.load(fh)",
        "        if 'versions' in data:",
        "            versions = data['versions']",
        "        if 'lockfile_sha256' in data:",
        "            lock = data['lockfile_sha256']",
    ]
    result = "    result = {'ok': True, 'reason': '', 'versions': versions, 'lockfile_sha256': lock"
    if interpreter is not None:
        result += ", 'interpreter': " + repr(interpreter)
    result += "}"
    lines += [
        result,
        "    return result",
        "",
        "",
        "def layout_errors(asset_file):",
        "    return []",
        "",
        "",
        "def surface(asset_file):",
        "    return {'names': []}",
        "",
        "",
        "def asset_runner(asset_file):",
        "    def run(entry, args):",
        "        return None",
        "    return run",
        "",
        "",
        "def strength_sites(asset_file):",
        "    return []",
        "",
        "",
        "def apply_site(asset_file, site):",
        "    return None",
        "",
    ]
    return "\n".join(lines)


class Fixture:
    pass


def make_repo(tmp_path, name):
    base = tmp_path / name
    repo = base / "repo"
    state = base / "state"
    state.mkdir(parents=True)
    py_state = state / "python.json"
    fake_state = state / "fake.json"
    py_state.write_text("{}")
    fake_state.write_text("{}")

    py_dir = repo / "gen" / "kind-python"
    py_dir.mkdir(parents=True)
    py_file = py_dir / "kind_python.py"
    py_file.write_text(
        adapter_source("python", {"python": "3.12.4", "packages": PK}, py_state, "/fake/python")
    )

    fake_dir = repo / "gen" / "kind-fake"
    fake_dir.mkdir(parents=True)
    fake_file = fake_dir / "kind_fake.py"
    fake_file.write_text(adapter_source("fake", {"fakec": "2.0.0"}, fake_state, None))

    arch = repo / "specs" / "architecture"
    arch.mkdir(parents=True)
    definition = arch / "asset-kind-fake.md"
    definition.write_text("# Asset kind fake\n\nA fixed fake definition.\n")

    comp = repo / "specs" / "components" / "foo"
    comp.mkdir(parents=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "assets: [fake:static/a.fake]\n"
        "---\n"
        "\n"
        "# Foo\n"
    )
    (repo / "gen" / "foo").mkdir(parents=True)

    P = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha(py_file),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    F = {
        "kind": "fake",
        "path": "static/a.fake",
        "definition_sha256": sha(definition),
        "adapter_sha256": sha(fake_file),
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    fx = Fixture()
    fx.repo = repo
    fx.py_state = py_state
    fx.fake_state = fake_state
    fx.definition = definition
    fx.P = P
    fx.F = F
    fx.E = [dict(P), dict(F)]
    return fx


def write_manifest(fx, assets, gate_versions=None):
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {} if gate_versions is None else gate_versions,
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
        "drivers": [],
    }
    (fx.repo / "gen" / "foo" / ".provenance.json").write_text(json.dumps(manifest))


def set_state(path, versions=None, lockfile=None, set_lock=False):
    data = {}
    if versions is not None:
        data["versions"] = versions
    if set_lock:
        data["lockfile_sha256"] = lockfile
    Path(path).write_text(json.dumps(data))


def check(fx):
    return provenance_checker.check_provenance("comp-foo", H, {}, fx.repo)


NEW_PY = {"python": "3.12.5", "packages": PK}


@pytest.mark.parametrize(
    "case",
    ["python_version", "python_packages", "fake_version", "fake_lockfile", "both"],
)
def test_versions_or_lockfile_only_is_environment_differs(tmp_path, case):
    fx = make_repo(tmp_path, case)
    write_manifest(fx, fx.E)
    if case == "python_version":
        set_state(fx.py_state, versions=NEW_PY)
    elif case == "python_packages":
        set_state(fx.py_state, versions={"python": "3.12.4", "packages": X})
    elif case == "fake_version":
        set_state(fx.fake_state, versions={"fakec": "2.1.0"})
    elif case == "fake_lockfile":
        set_state(fx.fake_state, lockfile=X, set_lock=True)
    elif case == "both":
        set_state(fx.py_state, versions=NEW_PY)
        set_state(fx.fake_state, versions={"fakec": "2.1.0"})
    result = check(fx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "environment differs"


@pytest.mark.parametrize(
    "case",
    ["definition_changed", "only_p", "reversed", "appended", "adapter_x", "no_definition_key"],
)
def test_other_asset_differences_keep_assets_differ(tmp_path, case):
    fx = make_repo(tmp_path, case)
    set_state(fx.py_state, versions=NEW_PY)
    E = fx.E
    if case == "definition_changed":
        assets = E
        write_manifest(fx, assets)
        fx.definition.write_text("# Asset kind fake\n\nA changed fake definition.\n")
    else:
        if case == "only_p":
            assets = [dict(fx.P)]
        elif case == "reversed":
            assets = [dict(E[1]), dict(E[0])]
        elif case == "appended":
            assets = [dict(E[0]), dict(E[1]), dict(E[1])]
        elif case == "adapter_x":
            fake = dict(E[1])
            fake["adapter_sha256"] = X
            assets = [dict(E[0]), fake]
        else:
            fake = dict(E[1])
            del fake["definition_sha256"]
            assets = [dict(E[0]), fake]
        write_manifest(fx, assets)
    result = check(fx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


@pytest.mark.parametrize(
    "gates, expected",
    [({"verifier": "v@0"}, "gates differ"), ({"generator": "g@0"}, "gate_versions differ")],
)
def test_gate_differences_come_before_environment(tmp_path, gates, expected):
    fx = make_repo(tmp_path, "gates_" + list(gates)[0])
    set_state(fx.py_state, versions=NEW_PY)
    write_manifest(fx, fx.E, gate_versions=gates)
    result = check(fx)
    assert field(result, "hit") is False
    assert field(result, "reason") == expected


def test_versions_set_back_is_hit(tmp_path):
    fx = make_repo(tmp_path, "back")
    write_manifest(fx, fx.E)
    set_state(fx.py_state, versions=NEW_PY)
    set_state(fx.fake_state, versions={"fakec": "2.1.0"}, lockfile=X, set_lock=True)
    first = check(fx)
    assert field(first, "hit") is False
    assert field(first, "reason") == "environment differs"
    set_state(fx.py_state, versions={"python": "3.12.4", "packages": PK})
    set_state(fx.fake_state, versions={"fakec": "2.0.0"}, lockfile=None, set_lock=True)
    result = check(fx)
    assert field(result, "hit") is True