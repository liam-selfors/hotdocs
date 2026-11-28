# hotdocs-criterion: sha256:994e57fe191c586b0b05e09426b77b8465972454bb108fdff0034660de3589ba
import os
import subprocess
from pathlib import Path

import run_environment


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_DRIVER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "NAME = " + repr("fake") + "\n"
    "FIXTURE = " + repr("fake_session") + "\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {" + repr("test_author") + ": " + repr("Fake driver text.") + "}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("")
    + ", " + repr("versions") + ": {" + repr("fakedrv") + ": " + repr("2.0") + "}, "
    + repr("lockfile_sha256") + ": None}\n"
    "\n"
    "\n"
    "class _Session:\n"
    "    def __init__(self, repo_root, work_dir):\n"
    "        self.value = " + repr("open") + "\n"
    "        self._repo_root = Path(repo_root)\n"
    "        self._work_dir = Path(work_dir)\n"
    "\n"
    "    def close(self):\n"
    "        with open(self._repo_root / " + repr("closed.log") + ", " + repr("a") + ") as f:\n"
    "            f.write(" + repr("closed\n") + ")\n"
    "        shots = self._work_dir / " + repr("screenshots") + "\n"
    "        shots.mkdir(parents=True, exist_ok=True)\n"
    "        (shots / " + repr("final-1.png") + ").write_bytes(" + repr(b"png1") + ")\n"
    "\n"
    "\n"
    "def open_session(repo_root, work_dir):\n"
    "    return _Session(repo_root, work_dir)\n"
)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "drivers: [fake]\n"
    "---\n"
    "\n"
    "# Foo\n"
)


TEST_SHOT_SOURCE = (
    "def test_shot(fake_session):\n"
    "    assert fake_session.value == " + repr("open") + "\n"
)


def _build_corpus(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD)

    drv_dir = repo_root / "gen" / "driver-fake"
    drv_dir.mkdir(parents=True)
    (drv_dir / "driver_fake.py").write_text(FAKE_DRIVER_SOURCE)

    (repo_root / "gen" / "foo").mkdir(parents=True)

    old_dir = repo_root / ".hotdocs" / "screenshots" / "foo" / "old"
    old_dir.mkdir(parents=True)
    (old_dir / "x.png").write_bytes(b"old")

    test_file = repo_root / "test_shot.py"
    test_file.write_text(TEST_SHOT_SOURCE)
    return test_file


def _run_pytest(env, repo_root, test_file, extra_env):
    run_env = dict(os.environ)
    run_env.pop("PYTEST_ADDOPTS", None)
    run_env.pop("HOTDOCS_SCREENSHOTS", None)
    run_env.update(extra_env)
    run_env["PYTHONPATH"] = str(field(env, "plugin_dir"))
    cmd = [
        str(field(env, "interpreter")),
        "-m",
        "pytest",
        *env.pytest_args(),
        "-p",
        "no:cacheprovider",
        "-q",
        str(test_file),
    ]
    return subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=run_env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _files_under(root):
    if not root.exists():
        return set()
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def test_ac_runenv_007(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    test_file = _build_corpus(repo_root)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is True, field(env, "failure_message")

        assert not (repo_root / ".hotdocs" / "screenshots" / "foo" / "old").exists()

        own_env = env.env_for(repo_root / "gen" / "foo")
        expected = str(repo_root.resolve() / ".hotdocs" / "screenshots" / "foo")
        assert own_env.get("HOTDOCS_SCREENSHOTS") == expected

        other_env = env.env_for(other_dir)
        assert "HOTDOCS_SCREENSHOTS" not in other_env

        first = _run_pytest(env, repo_root, test_file, own_env)
        assert first.returncode == 0, first.stdout + first.stderr

        shot = repo_root / ".hotdocs" / "screenshots" / "foo" / "test_shot" / "final-1.png"
        assert shot.is_file()
        assert shot.read_bytes() == b"png1"

        screenshots_root = repo_root / ".hotdocs" / "screenshots"
        before = _files_under(screenshots_root)

        second = _run_pytest(env, repo_root, test_file, other_env)
        assert second.returncode == 0, second.stdout + second.stderr

        after = _files_under(screenshots_root)
        assert after == before
    finally:
        env.close()