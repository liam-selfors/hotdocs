# hotdocs-criterion: sha256:6889625087b3bb779a92d23f9645d56b8b86918b10bb682dff6738e9c2395538
import os
import subprocess
from pathlib import Path

import run_environment


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
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
        "# Foo\n",
    )
    write(repo_root / "gen" / "foo" / "data" / "table.txt", "a=1\nb=2\n")

    write(
        repo_root / "specs" / "architecture" / "asset-kind-fake.md",
        "# Fake asset kind\n\nA fake kind for testing.\n",
    )
    kind_src = (
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
        "    return dict(names=[])\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return dict(ok=True, reason=" + repr("") + ", versions=dict(fake="
        + repr("1.0") + "), lockfile_sha256=None, interpreter=None)\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return dict(generator=" + repr("Fake generator text.")
        + ", test_author=" + repr("Fake kind text.") + ")\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    asset_file = Path(asset_file)\n"
        "\n"
        "    def run(entry, args):\n"
        "        for line in asset_file.read_text().splitlines():\n"
        "            prefix = entry + " + repr("=") + "\n"
        "            if line.startswith(prefix):\n"
        "                return int(line[len(prefix):])\n"
        "        raise AssetError(" + repr("no such entry") + ")\n"
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
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", kind_src)

    log_path = repo_root / "closed.log"
    driver_src = (
        "from pathlib import Path\n"
        "\n"
        "NAME = " + repr("fake") + "\n"
        "FIXTURE = " + repr("fake_session") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return dict(test_author=" + repr("Fake driver text.") + ")\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return dict(ok=True, reason=" + repr("") + ", versions=dict(fakedrv="
        + repr("2.0") + "), lockfile_sha256=None)\n"
        "\n"
        "\n"
        "class _Session:\n"
        "    def __init__(self, repo_root):\n"
        "        self.value = " + repr("open") + "\n"
        "        self._repo_root = Path(repo_root)\n"
        "\n"
        "    def close(self):\n"
        "        with open(self._repo_root / " + repr("closed.log") + ", "
        + repr("a") + ") as handle:\n"
        "            handle.write(" + repr("closed\n") + ")\n"
        "\n"
        "\n"
        "def open_session(repo_root, work_dir):\n"
        "    return _Session(repo_root)\n"
    )
    write(repo_root / "gen" / "driver-fake" / "driver_fake.py", driver_src)
    return log_path


def build_test_file(repo_root):
    expected = (
        "asset_runner: 'other.txt' is not a declared asset "
        "(declared: data/table.txt)"
    )
    src = (
        "import pytest\n"
        "\n"
        "\n"
        "def test_uses_asset_and_driver(asset_runner, fake_session):\n"
        "    assert asset_runner(" + repr("data/table.txt") + ")("
        + repr("b") + ", []) == 2\n"
        "    assert fake_session.value == " + repr("open") + "\n"
        "\n"
        "\n"
        "def test_undeclared_asset(asset_runner):\n"
        "    with pytest.raises(KeyError) as info:\n"
        "        asset_runner(" + repr("other.txt") + ")\n"
        "    assert info.value.args[0] == " + repr(expected) + "\n"
    )
    path = repo_root / "usage_tests" / "test_usage.py"
    write(path, src)
    return path


def test_ac_runenv_004(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = build_corpus(repo_root)
    test_file = build_test_file(repo_root)

    env_obj = run_environment.prepare("comp-foo", repo_root)
    closed = False
    try:
        assert field(env_obj, "ok") is True, field(env_obj, "failure_message")
        plugin_dir = field(env_obj, "plugin_dir")
        assert plugin_dir is not None
        assert Path(plugin_dir).is_dir()
        interpreter = field(env_obj, "interpreter")
        assert interpreter

        run_env = dict(os.environ)
        run_env.pop("PYTEST_ADDOPTS", None)
        run_env["PYTHONPATH"] = str(plugin_dir)
        run_env["PYTHONDONTWRITEBYTECODE"] = "1"
        run_env.update(env_obj.env_for(repo_root / "gen" / "foo"))

        cmd = [str(interpreter), "-m", "pytest", "-q"]
        cmd += list(env_obj.pytest_args())
        cmd += [str(test_file)]
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=run_env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

        assert log_path.is_file()
        assert log_path.read_text().splitlines() == ["closed"]

        env_obj.close()
        closed = True
        assert not Path(plugin_dir).exists()
    finally:
        if not closed:
            env_obj.close()