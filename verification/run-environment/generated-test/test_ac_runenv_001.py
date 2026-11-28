# hotdocs-criterion: sha256:9bc35b5f66732a81ac773f7e9139ff0029dd730cc3583648aa10ff75d2ccf0c9
import importlib.util
import sys
from pathlib import Path

import run_environment


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def close_env(env):
    closer = getattr(env, "close", None)
    if callable(closer):
        closer()


def write_component(repo_root, assets_line):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
    )
    if assets_line is not None:
        text += assets_line + "\n"
    text += "---\n\n# Foo\n"
    (comp_dir / "component.md").write_text(text)


def fake_kind_source(provisioned):
    if provisioned:
        report = {
            "ok": True,
            "reason": "",
            "versions": {"fake": "1.0"},
            "lockfile_sha256": None,
            "interpreter": None,
        }
    else:
        report = {
            "ok": False,
            "reason": "fake needs fakeprog >= 2",
            "versions": {},
            "lockfile_sha256": None,
            "interpreter": None,
        }
    return (
        "from pathlib import Path\n"
        "\n"
        "KIND = " + repr("fake") + "\n"
        "\n"
        "\n"
        "class AssetError(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return " + repr({"names": []}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return dict(" + repr(report) + ")\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "Fake generator text.",
                             "test_author": "Fake test author text."}) + "\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    asset_file = Path(asset_file)\n"
        "\n"
        "    def run(entry, args):\n"
        "        prefix = entry + " + repr("=") + "\n"
        "        for line in asset_file.read_text().splitlines():\n"
        "            if line.startswith(prefix):\n"
        "                return int(line[len(prefix):])\n"
        "        raise AssetError(" + repr("no entry: ") + " + entry)\n"
        "\n"
        "    return run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )


def plant_fake_kind(repo_root, provisioned):
    arch = repo_root / "specs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "asset-kind-fake.md").write_text("# Asset kind: fake\n\nFake kind.\n")
    kind_dir = repo_root / "gen" / "kind-fake"
    kind_dir.mkdir(parents=True, exist_ok=True)
    (kind_dir / "kind_fake.py").write_text(fake_kind_source(provisioned))
    data_dir = repo_root / "gen" / "foo" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "table.txt").write_text("a=1\nb=2\n")
    write_component(repo_root, "assets: [fake:data/table.txt]")


def real_python_interpreter(repo_root):
    path = Path(run_environment.__file__).parents[1] / "kind-python" / "kind_python.py"
    kind_python = load_module(path, "kind_python")
    return kind_python.provision(repo_root)["interpreter"]


def test_fake_kind_provisioned_uses_python_interpreter(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_fake_kind(repo_root, provisioned=True)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is True
        assert field(env, "failure_message") is None
        expected = real_python_interpreter(repo_root)
        assert field(env, "interpreter") == expected
    finally:
        close_env(env)


def test_unprovisioned_fake_kind_fails_with_reason(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_fake_kind(repo_root, provisioned=False)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is False
        assert field(env, "failure_message") == "fake needs fakeprog >= 2"
    finally:
        close_env(env)


def test_unknown_asset_kind_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(repo_root, "assets: [nokind:x.txt]")

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is False
        assert field(env, "failure_message") == "unknown asset kind: nokind"
    finally:
        close_env(env)