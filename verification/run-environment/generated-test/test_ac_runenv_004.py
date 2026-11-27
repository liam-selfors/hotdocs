# hotdocs-criterion: sha256:7f14120c29ec51f4d32d8839910948e4272c9b957464a1e2b5c3da480b74abc1
import os
import subprocess
from pathlib import Path

import run_environment


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


KIND_FAKE_SRC = (
    "from pathlib import Path\n"
    "\n"
    "KIND = 'fake'\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    asset_file = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in asset_file.read_text().splitlines():\n"
    "            if line.startswith(entry + '='):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise KeyError(entry)\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'fake': '1.0'}, 'lockfile_sha256': None}\n"
)

DRIVER_FAKE_SRC = (
    "from pathlib import Path\n"
    "\n"
    "NAME = 'fake'\n"
    "FIXTURE = 'fake_session'\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {'test_author': 'Fake driver text.'}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'fakedrv': '2.0'}, 'lockfile_sha256': None}\n"
    "\n"
    "\n"
    "class _Session:\n"
    "    def __init__(self, repo_root):\n"
    "        self.value = 'open'\n"
    "        self._log = Path(repo_root) / 'closed.log'\n"
    "\n"
    "    def close(self):\n"
    "        with open(self._log, 'a') as f:\n"
    "            f.write('closed\\n')\n"
    "\n"
    "\n"
    "def open_session(repo_root, work_dir):\n"
    "    return _Session(repo_root)\n"
)

EXPECTED_MESSAGE = (
    "asset_runner: 'other.txt' is not a declared asset (declared: data/table.txt)"
)

INNER_TEST_SRC = (
    "import pytest\n"
    "\n"
    "\n"
    "def test_runs_asset_and_driver(asset_runner, fake_session):\n"
    "    assert asset_runner('data/table.txt')('b', []) == 2\n"
    "    assert fake_session.value == 'open'\n"
    "\n"
    "\n"
    "def test_undeclared_asset(asset_runner):\n"
    "    with pytest.raises(KeyError) as info:\n"
    "        asset_runner('other.txt')\n"
    "    assert info.value.args[0] == " + repr(EXPECTED_MESSAGE) + "\n"
)


def build_corpus(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "assets: [fake:data/table.txt]\n"
        "drivers: [fake]\n"
        "---\n"
        "\n"
        "# Foo\n"
    )

    arch = repo_root / "specs" / "architecture"
    arch.mkdir(parents=True)
    (arch / "asset-kind-fake.md").write_text("# Fake kind\n\nAny text.\n")

    kind_dir = repo_root / "gen" / "kind-fake"
    kind_dir.mkdir(parents=True)
    (kind_dir / "kind_fake.py").write_text(KIND_FAKE_SRC)

    drv_dir = repo_root / "gen" / "driver-fake"
    drv_dir.mkdir(parents=True)
    (drv_dir / "driver_fake.py").write_text(DRIVER_FAKE_SRC)

    data_dir = repo_root / "gen" / "foo" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "table.txt").write_text("a=1\nb=2\n")


def test_ac_runenv_004(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    inner = repo_root / "test_inner.py"
    inner.write_text(INNER_TEST_SRC)

    env_obj = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env_obj, "ok") is True, field(env_obj, "failure_message")
        plugin_dir = field(env_obj, "plugin_dir")
        interpreter = field(env_obj, "interpreter")
        assert plugin_dir is not None
        assert interpreter is not None

        env = dict(os.environ)
        env.pop("PYTEST_ADDOPTS", None)
        env.pop("PYTEST_PLUGINS", None)
        env["PYTHONPATH"] = str(plugin_dir)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.update(env_obj.env_for(repo_root / "gen" / "foo"))

        cmd = [str(interpreter), "-m", "pytest"]
        cmd += list(env_obj.pytest_args())
        cmd += ["-p", "no:cacheprovider", str(inner)]
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

        log = repo_root / "closed.log"
        assert log.is_file()
        assert log.read_text().splitlines() == ["closed"]
    finally:
        env_obj.close()

    assert not Path(plugin_dir).exists()