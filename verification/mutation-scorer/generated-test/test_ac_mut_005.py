# hotdocs-criterion: sha256:8b831d14018a02c02d256fda2267e8792dd6dcb4be7f969bee240eaeb9010d66
import importlib.util
import sys
from pathlib import Path

import mutation_scorer


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_ADAPTER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "KIND = " + repr("fake") + "\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return []\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {" + repr("names") + ": []}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\n"
    "        " + repr("ok") + ": True,\n"
    "        " + repr("reason") + ": " + repr("") + ",\n"
    "        " + repr("versions") + ": {" + repr("fake") + ": " + repr("1.0") + "},\n"
    "        " + repr("lockfile_sha256") + ": None,\n"
    "        " + repr("interpreter") + ": None,\n"
    "    }\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {" + repr("generator") + ": " + repr("fake generator") + ", "
    + repr("test_author") + ": " + repr("fake test author") + "}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    asset_file = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in asset_file.read_text().splitlines():\n"
    "            if line.startswith(entry + " + repr("=") + "):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise KeyError(entry)\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    raise ValueError(" + repr("bad site") + ")\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    asset_file = Path(asset_file)\n"
    "    lines = asset_file.read_text().splitlines()\n"
    "    index = int(site[" + repr("description") + "].split(" + repr(":") + ")[0]) - 1\n"
    "    key, value = lines[index].split(" + repr("=") + ", 1)\n"
    "    lines[index] = key + " + repr("=") + " + str(int(value) + 1)\n"
    "    asset_file.write_text(" + repr("\n") + ".join(lines) + " + repr("\n") + ")\n"
)


def build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "qux"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/qux/\n"
        "assets: [fake:data/table.txt]\n"
        "---\n"
        "\n"
        "# Qux\n"
    )

    arch = repo_root / "specs" / "architecture"
    arch.mkdir(parents=True)
    (arch / "asset-kind-fake.md").write_text("# Fake kind\n\nAny text.\n")

    kind_dir = repo_root / "gen" / "kind-fake"
    kind_dir.mkdir(parents=True)
    (kind_dir / "kind_fake.py").write_text(FAKE_ADAPTER_SOURCE)

    code_dir = repo_root / "gen" / "qux"
    (code_dir / "data").mkdir(parents=True)
    (code_dir / "qux.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
    )
    (code_dir / "data" / "table.txt").write_text("a=1\nb=2\n")


def test_ac_mut_005_adapter_strength_sites_failure(tmp_path_factory):
    repo_root = tmp_path_factory.mktemp("repo")
    tests_dir = tmp_path_factory.mktemp("tests")
    build_fixture(repo_root)

    test_file = tests_dir / "test_qux_passing.py"
    test_file.write_text(
        "import qux\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert qux.add(2, 3) == 5\n"
    )

    run_env_path = (
        Path(mutation_scorer.__file__).resolve().parents[1]
        / "run-environment"
        / "run_environment.py"
    )
    run_environment = load_module(run_env_path, "run_environment")

    environment = run_environment.prepare("comp-qux", repo_root)
    try:
        assert field(environment, "ok") is True, field(environment, "failure_message")

        result = mutation_scorer.score(
            "comp-qux", repo_root, [str(test_file.resolve())], environment
        )

        assert field(result, "mutation_score") is None
        assert (
            field(result, "mutation_error")
            == "fake adapter failed: ValueError: bad site"
        )
    finally:
        environment.close()