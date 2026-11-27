# hotdocs-criterion: sha256:6b5871fcfc85f4374ad1bf6833e58247f5d8bce573e2879880b027041a6ae87e
import json
import platform
import subprocess
import sys

import kind_python


PROGRAM = "\n".join([
    r"import hashlib,json,platform,re",
    r"from importlib.metadata import distributions as ds",
    r"s=sorted({re.sub(r'[-_.]+','-',str(d.metadata['Name']).lower())+'=='+str(d.version) for d in ds()})",
    r"print(json.dumps({'python':platform.python_version(),'packages':'sha256:'+hashlib.sha256('\n'.join(s).encode()).hexdigest()}))",
])


def envinfo(python):
    proc = subprocess.run(
        [python, "-I", "-c", PROGRAM], capture_output=True, text=True
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_ac_kpy_006_provision_without_lock_uses_running_interpreter(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    assert not (tmp_path / "environments" / "python" / "requirements.lock").exists()

    result = kind_python.provision(tmp_path)

    expected_versions = envinfo(sys.executable)
    assert expected_versions["python"] == platform.python_version()

    assert isinstance(result, dict)
    assert result == {
        "ok": True,
        "reason": "",
        "versions": expected_versions,
        "lockfile_sha256": None,
        "interpreter": sys.executable,
    }
    assert result["versions"]["python"] == platform.python_version()

    assert list(tmp_path.iterdir()) == []