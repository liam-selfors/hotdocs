# hotdocs-criterion: sha256:50668154ae6081031a0bdfad794bbb5506332d12c866785d41c2c8a9455c37ba
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


def load_run_environment():
    path = (
        Path(mutation_scorer.__file__).resolve().parents[1]
        / "run-environment"
        / "run_environment.py"
    )
    return load_module(path, "run_environment")


FAKE_ADAPTER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "KIND = 'fake'\n"
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
    "    return {'names': []}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'fake': '1.0'},\n"
    "            'lockfile_sha256': None, 'interpreter': None}\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': 'fake generator', 'test_author': 'fake test author'}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    asset_file = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in asset_file.read_text().splitlines():\n"
    "            if line.startswith(entry + '='):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise AssetError('no entry ' + repr(entry))\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    asset_file = Path(asset_file)\n"
    "    lines = asset_file.read_text().splitlines()\n"
    "    index = int(site['description'].split(':')[0]) - 1\n"
    "    key, value = lines[index].split('=', 1)\n"
    "    lines[index] = key + '=' + str(int(value) + 1)\n"
    "    asset_file.write_text('\\n'.join(lines) + '\\n')\n"
)


def build_repo(repo_root, code, assets_line=None, fake_kind=False):
    comp_dir = repo_root / "specs" / "components" / "qux"
    comp_dir.mkdir(parents=True)
    front = (
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "sealed: true\n"
        "source_path: legacy/qux/\n"
    )
    if fake_kind:
        front += "depends_on: [comp-kind-fake]\n"
    else:
        front += "depends_on: []\n"
    if assets_line is not None:
        front += assets_line + "\n"
    front += "---\n\n# Qux\n"
    (comp_dir / "component.md").write_text(front)

    code_dir = repo_root / "gen" / "qux"
    code_dir.mkdir(parents=True)
    (code_dir / "qux.py").write_text(code)

    if fake_kind:
        arch = repo_root / "specs" / "architecture"
        arch.mkdir(parents=True, exist_ok=True)
        (arch / "asset-kind-fake.md").write_text("# Fake kind\n\nA fake kind for tests.\n")
        kind_dir = repo_root / "gen" / "kind-fake"
        kind_dir.mkdir(parents=True)
        (kind_dir / "kind_fake.py").write_text(FAKE_ADAPTER_SOURCE)
        data_dir = code_dir / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "table.txt").write_text("a=1\nb=2\n")


def write_tests(test_dir, files):
    test_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, content in files:
        p = test_dir / name
        p.write_text(content)
        paths.append(str(p.resolve()))
    return paths


def run_score(repo_root, tests):
    run_environment = load_run_environment()
    env = run_environment.prepare("comp-qux", repo_root)
    try:
        assert field(env, "ok") is True, field(env, "failure_message")
        return mutation_scorer.score("comp-qux", repo_root, tests, env)
    finally:
        env.close()


QUX_FOUR_FUNCTIONS = (
    "def g(a, b):\n"
    "    return a < b\n"
    "\n"
    "\n"
    "def h(a, b):\n"
    "    return a // b\n"
    "\n"
    "\n"
    "def m(k, d):\n"
    "    return k in d\n"
    "\n"
    "\n"
    "def do_the_thing(x):\n"
    "    return x\n"
)


def test_score_is_killed_over_all_mutants(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, QUX_FOUR_FUNCTIONS)
    tests = write_tests(
        tmp_path / "tests",
        [
            (
                "test_qux_g.py",
                "import qux\n"
                "\n"
                "\n"
                "def test_g():\n"
                "    assert qux.g(1, 2) is True\n"
                "    assert qux.g(2, 1) is False\n"
                "    assert qux.g(1, 1) is False\n",
            )
        ],
    )

    result = run_score(repo_root, tests)

    assert field(result, "mutation_error") is None
    assert field(result, "mutants") == 3
    assert field(result, "killed") == 1
    assert field(result, "mutation_score") == 1 / 3


def test_score_is_one_over_both_tests(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(
        repo_root,
        "def f1(a, b):\n"
        "    return a < b\n"
        "\n"
        "\n"
        "def f2(a, b):\n"
        "    return a > b\n",
    )
    tests = write_tests(
        tmp_path / "tests",
        [
            (
                "test_qux_f1.py",
                "import qux\n"
                "\n"
                "\n"
                "def test_f1():\n"
                "    assert qux.f1(1, 2) is True\n"
                "    assert qux.f1(2, 1) is False\n"
                "    assert qux.f1(1, 1) is False\n",
            ),
            (
                "test_qux_f2.py",
                "import qux\n"
                "\n"
                "\n"
                "def test_f2():\n"
                "    assert qux.f2(2, 1) is True\n"
                "    assert qux.f2(1, 2) is False\n"
                "    assert qux.f2(1, 1) is False\n",
            ),
        ],
    )

    result = run_score(repo_root, tests)

    assert field(result, "mutation_error") is None
    assert field(result, "mutation_score") == 1.0


def _asset_case(tmp_path, test_body):
    repo_root = tmp_path / "repo"
    build_repo(
        repo_root,
        "def qux():\n"
        "    return None\n",
        assets_line="assets: [fake:data/table.txt]",
        fake_kind=True,
    )
    tests = write_tests(
        tmp_path / "tests",
        [
            (
                "test_qux_asset.py",
                "import qux\n"
                "\n"
                "\n"
                "def test_asset(asset_runner):\n"
                "    assert qux.qux() is None\n" + test_body,
            )
        ],
    )
    return run_score(repo_root, tests)


def test_asset_sites_count_in_the_one_score(tmp_path):
    line_a = "    assert asset_runner(" + repr("data/table.txt") + ")(" + repr("a") + ", []) == 1\n"
    line_b = "    assert asset_runner(" + repr("data/table.txt") + ")(" + repr("b") + ", []) == 2\n"

    result = _asset_case(tmp_path / "only_a", line_a)
    assert field(result, "mutation_error") is None
    assert field(result, "mutation_score") == 0.5

    result = _asset_case(tmp_path / "a_and_b", line_a + line_b)
    assert field(result, "mutation_error") is None
    assert field(result, "mutation_score") == 1.0