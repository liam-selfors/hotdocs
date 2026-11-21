# hotdocs-criterion: sha256:a1f12c2849dd1f48b80d8a39d2f208c9074ff3c7423d003709fb456289450ce3
import hashlib
import platform
import sys

import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _pin_path(repo_root):
    return repo_root / "environments" / "python" / "python-version"


def _lock_path(repo_root):
    return repo_root / "environments" / "python" / "requirements.lock"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_pin_major_minor_matches(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    mm = "%d.%d" % sys.version_info[:2]
    _write(_pin_path(tmp_path), mm + "\n")

    result = kind_python.provision(tmp_path)

    assert field(result, "ok") is True
    assert field(result, "reason") == ""
    assert field(result, "interpreter") == sys.executable


def test_pin_full_version_matches(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    pv = platform.python_version()
    _write(_pin_path(tmp_path), pv)

    result = kind_python.provision(tmp_path)

    assert field(result, "ok") is True
    assert field(result, "reason") == ""
    assert field(result, "interpreter") == sys.executable


def test_pin_text_prefix_but_not_version_prefix_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    pv = platform.python_version()
    _write(_pin_path(tmp_path), "3.1\n")

    result = kind_python.provision(tmp_path)

    assert dict(result) == {
        "ok": False,
        "reason": "python environment: needs Python 3.1, found " + pv,
        "versions": {},
        "lockfile_sha256": None,
        "interpreter": None,
    }


def test_pin_mismatch_with_lock_reports_lock_hash_and_creates_nothing(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    pv = platform.python_version()
    _write(_pin_path(tmp_path), "2.7")
    lock = _lock_path(tmp_path)
    _write(lock, "--no-index\npytest==8.0.0\n")
    lock_bytes = lock.read_bytes()

    result = kind_python.provision(tmp_path)

    assert dict(result) == {
        "ok": False,
        "reason": "python environment: needs Python 2.7, found " + pv,
        "versions": {},
        "interpreter": None,
        "lockfile_sha256": "sha256:" + hashlib.sha256(lock_bytes).hexdigest(),
    }
    assert not (tmp_path / ".hotdocs").exists()