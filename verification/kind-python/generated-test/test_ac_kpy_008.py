# hotdocs-criterion: sha256:c9865a92cf67a7e8ed7a528e7268edc3dc0230a7710386a76958ea2b1479a67a
import hashlib
import json
import platform
import subprocess
import sys
import zipfile

import pytest

import kind_python


# R-KPY-004's environment program: python's full version and the sha256 of
# the sorted, distinct "<normalized name>==<version>" lines of the installed
# distributions, joined with "\n".
PROGRAM = (
    "import hashlib, json, platform, re\n"
    "from importlib import metadata\n"
    "lines = sorted({re.sub(r'[-_.]+', '-', d.metadata['Name']).lower() + '==' + d.version for d in metadata.distributions() if d.metadata['Name']})\n"
    "print(json.dumps({'python': platform.python_version(), 'packages': 'sha256:' + hashlib.sha256('\\n'.join(lines).encode('utf-8')).hexdigest()}))\n"
)


def envinfo(python):
    proc = subprocess.run([python, "-I", "-c", PROGRAM], capture_output=True, text=True)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_dict(value):
    names = ["ok", "reason", "versions", "interpreter", "lockfile_sha256"]
    if isinstance(value, dict):
        return dict(value)
    return {name: field(value, name) for name in names}


def lock_hash(lock):
    return "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest()


def build_wheel(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    wheel = wheels / "pytest-0.0.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr(
            "pytest-0.0.1.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: pytest\nVersion: 0.0.1\n",
        )
        zf.writestr(
            "pytest-0.0.1.dist-info/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        zf.writestr("pytest-0.0.1.dist-info/RECORD", "")
    return wheels


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX layout (bin/python)")
def test_ac_kpy_008(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    env = tmp_path / ".hotdocs" / "env" / "python"
    interpreter = str(env / "bin" / "python")
    marker = env / ".lock-sha256"
    v = platform.python_version()

    lock_dir = tmp_path / "environments" / "python"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = lock_dir / "requirements.lock"

    # Part 1: a lock pip cannot satisfy offline.
    lock.write_text("--no-index\nPyTest==99.0.0\n", encoding="utf-8")
    h = lock_hash(lock)
    result = as_dict(kind_python.provision(tmp_path))
    assert result == {
        "ok": False,
        "reason": "python environment: ERROR: No matching distribution found for PyTest==99.0.0",
        "versions": {},
        "interpreter": None,
        "lockfile_sha256": h,
    }
    assert (env / "bin" / "python").exists()
    assert not marker.exists()
    assert (tmp_path / ".hotdocs" / "env" / "python.lock").exists()

    # Part 2: the local lock.
    wheels = build_wheel(tmp_path)
    lock.write_text(
        "--no-index\n--find-links " + str(wheels) + "\npytest==0.0.1\n",
        encoding="utf-8",
    )
    h = lock_hash(lock)

    first = as_dict(kind_python.provision(tmp_path))
    expected = {
        "ok": True,
        "reason": "",
        "versions": envinfo(interpreter),
        "lockfile_sha256": h,
        "interpreter": interpreter,
    }
    assert first == expected
    assert marker.read_text(encoding="utf-8") == h + " " + v

    second = as_dict(kind_python.provision(tmp_path))
    assert second == expected
    assert marker.read_text(encoding="utf-8") == h + " " + v

    # Part 3: a stale marker forces a rebuild.
    marker.write_text("stale")
    third = as_dict(kind_python.provision(tmp_path))
    assert third == expected
    assert marker.read_text(encoding="utf-8") == h + " " + v