# hotdocs-criterion: sha256:0e1de94d31073e5ad3bb80df13249fd8d6873d821177819d3d4a2621db8f1f85
import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_dict(result):
    keys = ["ok", "reason", "versions", "interpreter", "lockfile_sha256"]
    if isinstance(result, dict):
        return dict(result)
    return {k: field(result, k) for k in keys}


def lock_hash(lock):
    return "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest()


ENVINFO_PROGRAM = (
    "import hashlib, json, platform, re\n"
    "import importlib.metadata as m\n"
    "lines = set()\n"
    "for d in m.distributions():\n"
    "    name = d.metadata['Name']\n"
    "    if not name:\n"
    "        continue\n"
    "    lines.add(re.sub(r'[-_.]+', '-', name).lower() + '==' + d.version)\n"
    "text = '\\n'.join(sorted(lines))\n"
    "print(json.dumps({'python': platform.python_version(),"
    " 'packages': 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest()}))\n"
)


def envinfo(interpreter):
    proc = subprocess.run(
        [interpreter, "-I", "-c", ENVINFO_PROGRAM],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return json.loads(lines[-1])


def record_hash(data):
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_local_wheel(directory):
    directory.mkdir(parents=True, exist_ok=True)
    wheel = directory / "pytest-99.0.0-py3-none-any.whl"
    dist_info = "pytest-99.0.0.dist-info"
    files = {
        "pytest/__init__.py": b"",
        dist_info + "/METADATA": (
            b"Metadata-Version: 2.1\nName: pytest\nVersion: 99.0.0\n"
        ),
        dist_info + "/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: test\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    record_lines = []
    for name, data in files.items():
        record_lines.append(name + "," + record_hash(data) + "," + str(len(data)))
    record_lines.append(dist_info + "/RECORD,,")
    files[dist_info + "/RECORD"] = ("\n".join(record_lines) + "\n").encode("utf-8")
    with zipfile.ZipFile(wheel, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return directory


@pytest.mark.skipif(os.name == "nt", reason="POSIX layout (bin/python)")
def test_ac_kpy_008(tmp_path):
    try:
        import ensurepip  # noqa: F401
        import venv  # noqa: F401
    except ImportError:
        pytest.skip("venv/ensurepip not available")

    lock_dir = tmp_path / "environments" / "python"
    lock_dir.mkdir(parents=True)
    lock = lock_dir / "requirements.lock"
    env = tmp_path / ".hotdocs" / "env" / "python"
    interpreter = str(env / "bin" / "python")
    marker = env / ".lock-sha256"
    v = platform.python_version()

    # Failing install, offline.
    lock.write_bytes(b"--no-index\nPyTest==99.0.0\n")
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

    # A local lock: offline, from a local wheel that pins pytest.
    wheels = build_local_wheel(tmp_path / "wheels")
    lock.write_bytes(
        (
            "--no-index\n"
            "--find-links " + str(wheels) + "\n"
            "pytest==99.0.0\n"
        ).encode("utf-8")
    )

    for _ in range(2):
        h = lock_hash(lock)
        result = as_dict(kind_python.provision(tmp_path))
        expected = {
            "ok": True,
            "reason": "",
            "versions": envinfo(interpreter),
            "lockfile_sha256": h,
            "interpreter": interpreter,
        }
        assert result == expected
        assert marker.read_text() == h + " " + v

    marker.write_text("stale")
    h = lock_hash(lock)
    result = as_dict(kind_python.provision(tmp_path))
    expected = {
        "ok": True,
        "reason": "",
        "versions": envinfo(interpreter),
        "lockfile_sha256": h,
        "interpreter": interpreter,
    }
    assert result == expected
    assert marker.read_text() == h + " " + v