# hotdocs-criterion: sha256:f9f60654cd7591107fc1593837458cf9ae0d42ebab90f1cb12d3d26849079b74
import os
import subprocess
from pathlib import Path

import run_environment


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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

DRIVER_SRC = (
    "from pathlib import Path\n"
    "\n"
    "NAME = " + repr("fake") + "\n"
    "FIXTURE = " + repr("fake_session") + "\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return " + repr({"test_author": "Fake driver text."}) + "\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return " + repr({"ok": True, "reason": "", "versions": {"fakedrv": "2.0"},
                          "lockfile_sha256": None}) + "\n"
    "\n"
    "\n"
    "class _Session:\n"
    "    def __init__(self, repo_root, work_dir):\n"
    "        self.value = " + repr("open") + "\n"
    "        self._repo_root = Path(repo_root)\n"
    "        self._work_dir = Path(work_dir)\n"
    "\n"
    "    def close(self):\n"
    "        shots = self._work_dir / " + repr("screenshots") + "\n"
    "        shots.mkdir(parents=True, exist_ok=True)\n"
    "        (shots / " + repr("final-1.png") + ").write_bytes(" + repr(b"png1") + ")\n"
    "        with open(self._repo_root / " + repr("closed.log") + ", " + repr("a") + ") as f:\n"
    "            f.write(" + repr("closed\n") + ")\n"
    "\n"
    "\n"
    "def open_session(repo_root, work_dir):\n"
    "    return _Session(repo_root, work_dir)\n"
)

TEST_SHOT_SRC = (
    "def test_shot(fake_session):\n"
    "    assert fake_session.value == " + repr("open") + "\n"
)


def snapshot(root):
    result = {}
    if not root.exists():
        return result
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_dir():
            result[rel + "/"] = None
        else:
            result[rel] = p.read_bytes()
    return result


def run_pytest(env, test_file, repo_root, extra_env):
    child_env = {k: v for k, v in os.environ.items() if not k.startswith("HOTDOCS_")}
    child_env.update(extra_env)
    child_env["PYTHONPATH"] = str(field(env, "plugin_dir"))
    cmd = [str(field(env, "interpreter")), "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    cmd += list(env.pytest_args())
    cmd.append(str(test_file))
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return proc


def test_ac_runenv_007(tmp_path, tmp_path_factory):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD)

    drv_dir = repo_root / "gen" / "driver-fake"
    drv_dir.mkdir(parents=True)
    (drv_dir / "driver_fake.py").write_text(DRIVER_SRC)

    (repo_root / "gen" / "foo").mkdir(parents=True)

    shots_root = repo_root / ".hotdocs" / "screenshots"
    old_x = shots_root / "foo" / "old" / "x.png"
    old_x.parent.mkdir(parents=True)
    old_x.write_bytes(b"oldx")
    stale = shots_root / "foo" / "test_shot" / "stale.png"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")

    tests_dir = repo_root / "shot_tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_shot.py"
    test_file.write_text(TEST_SHOT_SRC)

    other_dir = tmp_path_factory.mktemp("other_code")

    before = snapshot(shots_root)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is True, field(env, "failure_message")
        assert snapshot(shots_root) == before

        env_gen = env.env_for(repo_root / "gen" / "foo")
        assert snapshot(shots_root) == before

        env_other = env.env_for(other_dir)
        assert snapshot(shots_root) == before

        expected = str(repo_root.resolve() / ".hotdocs" / "screenshots" / "foo")
        assert env_gen.get("HOTDOCS_SCREENSHOTS") == expected
        assert "HOTDOCS_SCREENSHOTS" not in env_other

        proc1 = run_pytest(env, test_file, repo_root, env_gen)
        assert proc1.returncode == 0, proc1.stdout + proc1.stderr

        shot_dir = shots_root / "foo" / "test_shot"
        assert shot_dir.is_dir()
        assert sorted(p.name for p in shot_dir.iterdir()) == ["final-1.png"]
        assert (shot_dir / "final-1.png").read_bytes() == b"png1"
        assert not stale.exists()
        assert old_x.is_file()
        assert old_x.read_bytes() == b"oldx"

        after_first = snapshot(shots_root)

        proc2 = run_pytest(env, test_file, repo_root, env_other)
        assert proc2.returncode == 0, proc2.stdout + proc2.stderr

        assert snapshot(shots_root) == after_first

        log = repo_root / "closed.log"
        assert log.read_text().splitlines() == ["closed", "closed"]
    finally:
        env.close()