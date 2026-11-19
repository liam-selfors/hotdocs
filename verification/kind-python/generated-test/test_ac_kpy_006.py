# hotdocs-criterion: sha256:b0d0aef5704df4798645739a6729713cc180a086ec61daedb693a33e18457083
import json
import platform
import subprocess
import sys
from pathlib import Path

import kind_python


PROGRAM = "\n".join([
    "import hashlib,json,platform,re",
    "from importlib.metadata import distributions as ds",
    "s=sorted({re.sub(r'[-_.]+','-',str(d.metadata['Name']).lower())+'=='+str(d.version) for d in ds()})",
    "print(json.dumps({'python':platform.python_version(),'packages':'sha256:'+hashlib.sha256('\\n'.join(s).encode()).hexdigest()}))",
])


def envinfo(interpreter):
    proc = subprocess.run(
        [interpreter, "-I", "-c", PROGRAM],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_ac_kpy_006_no_lock_uses_running_interpreter(tmp_path):
    root = Path(tmp_path)
    assert not (root / "environments" / "python" / "requirements.lock").exists()
    assert list(root.iterdir()) == []

    result = kind_python.provision(root)

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

    assert list(root.iterdir()) == []