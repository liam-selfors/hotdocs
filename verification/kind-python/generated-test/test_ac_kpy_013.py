# hotdocs-criterion: sha256:debfbc8a84b1b9376e60c600fa701b857f3c236e6d4a39d4227fb8ec5fc4f72c
import hashlib
import platform
import sys
from pathlib import Path

import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _pin_dir(repo_root):
    d = Path(repo_root) / "environments" / "python"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_ac_kpy_013_pin_matches_major_minor(tmp_path):
    mm = "%d.%d" % sys.version_info[:2]
    d = _pin_dir(tmp_path)
    (d / "python-version").write_text(mm + "\n")
    assert not (d / "requirements.lock").exists()

    result = kind_python.provision(tmp_path)

    assert field(result, "ok") is True
    assert field(result, "reason") == ""
    assert field(result, "interpreter") == sys.executable


def test_ac_kpy_013_pin_matches_full_version(tmp_path):
    pv = platform.python_version()
    d = _pin_dir(tmp_path)
    (d / "python-version").write_text(pv)

    result = kind_python.provision(tmp_path)

    assert field(result, "ok") is True
    assert field(result, "reason") == ""
    assert field(result, "interpreter") == sys.executable


def test_ac_kpy_013_text_prefix_is_not_version_prefix(tmp_path):
    pv = platform.python_version()
    d = _pin_dir(tmp_path)
    (d / "python-version").write_text("3.1\n")

    result = kind_python.provision(tmp_path)

    assert result == {
        "ok": False,
        "reason": "python environment: needs Python 3.1, found " + pv,
        "versions": {},
        "lockfile_sha256": None,
        "interpreter": None,
    }


def test_ac_kpy_013_pin_mismatch_with_lock_creates_nothing(tmp_path):
    pv = platform.python_version()
    d = _pin_dir(tmp_path)
    (d / "python-version").write_text("2.7")
    lock = d / "requirements.lock"
    lock.write_bytes(b"--no-index\npytest==8.0.0\n")
    lock_bytes = lock.read_bytes()

    result = kind_python.provision(tmp_path)

    assert result == {
        "ok": False,
        "reason": "python environment: needs Python 2.7, found " + pv,
        "versions": {},
        "interpreter": None,
        "lockfile_sha256": "sha256:" + hashlib.sha256(lock_bytes).hexdigest(),
    }
    assert not (tmp_path / ".hotdocs").exists()