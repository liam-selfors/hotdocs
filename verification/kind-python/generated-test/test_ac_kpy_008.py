# hotdocs-criterion: sha256:6d1694e28fb5c5e724748dd83993da41e5dfcd7516d90de34a6890fe4c3e8c41
import hashlib
import json
import platform
import subprocess
import zipfile

import kind_python


# R-KPY-004's environment program is not in this bundle. This reconstructs it from
# asset-kind-python.md "## Environment": {"python": platform.python_version(),
# "packages": "sha256:<hex>"}, the hash taken over the sorted, distinct
# "<normalized name>==<version>" lines joined with "\n".
PROGRAM = (
    "import hashlib, importlib.metadata, json, platform, re\n"
    "lines = sorted({re.sub(r'[-_.]+', '-', d.metadata['Name']).lower() + '==' + d.version for d in importlib.metadata.distributions() if d.metadata['Name']})\n"
    "packages = 'sha256:' + hashlib.sha256('\\n'.join(lines).encode('utf-8')).hexdigest()\n"
    "print(json.dumps({'python': platform.python_version(), 'packages': packages}))\n"
)


def envinfo(python):
    proc = subprocess.run([python, "-I", "-c", PROGRAM], capture_output=True, text=True)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def lock_hash(lock):
    return "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest()


def build_wheel(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    whl = wheels / "pytest-0.0.1-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as zf:
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


def test_ac_kpy_008(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    env = tmp_path / ".hotdocs" / "env" / "python"
    marker = env / ".lock-sha256"
    interpreter = str(env / "bin" / "python")
    v = platform.python_version()

    lock = tmp_path / "environments" / "python" / "requirements.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)

    # Failing install: an unavailable pin, offline.
    lock.write_text("--no-index\nPyTest==99.0.0\n", encoding="utf-8")
    h = lock_hash(lock)
    result = kind_python.provision(tmp_path)
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

    # The local lock of testing.md.
    build_wheel(tmp_path)
    lock.write_text(
        "--no-index\n--find-links " + str(tmp_path / "wheels") + "\npytest==0.0.1\n",
        encoding="utf-8",
    )

    for _ in range(2):
        h = lock_hash(lock)
        result = kind_python.provision(tmp_path)
        expected = {
            "ok": True,
            "reason": "",
            "versions": envinfo(interpreter),
            "lockfile_sha256": h,
            "interpreter": interpreter,
        }
        assert result == expected
        assert marker.read_text(encoding="utf-8") == h + " " + v

    # A stale marker forces a rebuild.
    marker.write_text("stale")
    h = lock_hash(lock)
    result = kind_python.provision(tmp_path)
    expected = {
        "ok": True,
        "reason": "",
        "versions": envinfo(interpreter),
        "lockfile_sha256": h,
        "interpreter": interpreter,
    }
    assert result == expected
    assert marker.read_text(encoding="utf-8") == h + " " + v