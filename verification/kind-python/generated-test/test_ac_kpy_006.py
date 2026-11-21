# hotdocs-criterion: sha256:df241dfcdbc2354fbe438a32424c8448200920e5448ad7ececfd9c08ee875a04
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
    completed = subprocess.run(
        [python, "-I", "-c", PROGRAM], capture_output=True, text=True
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_ac_kpy_006_no_lock_uses_running_interpreter(tmp_path, monkeypatch):
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