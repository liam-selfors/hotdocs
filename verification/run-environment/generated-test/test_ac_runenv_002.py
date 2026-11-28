# hotdocs-criterion: sha256:9ee49c683003a8acceaf4e9c4ddd5ec92fa699cc2556014fd2922f59c9e5a513
import hashlib
import importlib.util
import sys
from pathlib import Path

import run_environment


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_component(repo_root, assets_line, depends_on_line=None):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team]",
    ]
    if depends_on_line is not None:
        lines.append(depends_on_line)
    lines += [
        "sealed: true",
        "source_path: legacy/foo/",
        assets_line,
        "---",
        "",
        "# Foo",
        "",
    ]
    (comp_dir / "component.md").write_text("\n".join(lines), encoding="utf-8")


FAKE_ADAPTER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "KIND = " + repr("fake") + "\n"
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
    "        raise KeyError(entry)\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("")
    + ", " + repr("versions") + ": {" + repr("fake") + ": " + repr("1.0") + "}, "
    + repr("lockfile_sha256") + ": None}\n"
)


def real_python_adapter_path():
    return Path(run_environment.__file__).parents[1] / "kind-python" / "kind_python.py"


def expected_python_versions(repo_root):
    module = load_module(real_python_adapter_path(), "kind_python")
    return field(module.provision(repo_root), "versions")


def test_fake_kind_assets_entries(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(repo_root, "assets: [fake:data/table.txt]",
                    "depends_on: [comp-kind-fake]")
    definition = repo_root / "specs" / "architecture" / "asset-kind-fake.md"
    definition.parent.mkdir(parents=True, exist_ok=True)
    definition.write_text("# Fake asset kind\n\nAny text.\n", encoding="utf-8")
    adapter = repo_root / "gen" / "kind-fake" / "kind_fake.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(FAKE_ADAPTER_SOURCE, encoding="utf-8")
    table = repo_root / "gen" / "foo" / "data" / "table.txt"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text("a=1\nb=2\n", encoding="utf-8")

    expected_versions = expected_python_versions(repo_root)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assets = list(field(env, "assets"))
        assert len(assets) == 2

        first = assets[0]
        assert field(first, "kind") == "python"
        assert field(first, "path") == "."
        assert field(first, "versions") == expected_versions

        second = assets[1]
        assert field(second, "kind") == "fake"
        assert field(second, "path") == "data/table.txt"
        def_hash = field(second, "definition_sha256")
        adapter_hash = field(second, "adapter_sha256")
        assert def_hash == sha(definition)
        assert adapter_hash == sha(adapter)
        for h in (def_hash, adapter_hash):
            assert h.startswith("sha256:")
            hexpart = h[len("sha256:"):]
            assert len(hexpart) == 64
            assert hexpart == hexpart.lower()
        assert field(second, "versions") == {"fake": "1.0"}
        assert field(second, "lockfile_sha256") is None
    finally:
        env.close()


def test_kind_with_no_definition_or_adapter(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(repo_root, "assets: [nokind:x.txt]")

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assets = list(field(env, "assets"))
        assert len(assets) == 2
        assert field(assets[0], "kind") == "python"
        assert field(assets[0], "path") == "."

        second = assets[1]
        assert field(second, "kind") == "nokind"
        assert field(second, "path") == "x.txt"
        assert field(second, "adapter_sha256") is None
        assert field(second, "definition_sha256") is None
        assert field(second, "versions") == {}
        assert field(second, "lockfile_sha256") is None
    finally:
        env.close()