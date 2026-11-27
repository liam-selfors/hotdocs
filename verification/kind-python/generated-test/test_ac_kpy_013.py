# hotdocs-criterion: sha256:8588ec700a9d6a421ad8beceb481123b2a4d9cce42e844a876129e3d6cae5926
import hashlib
import platform
import sys

import kind_python


KEYS = ("ok", "reason", "versions", "lockfile_sha256", "interpreter")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_dict(value):
    if isinstance(value, dict):
        return dict(value)
    return {k: getattr(value, k) for k in KEYS}


def write_pin(repo_root, text):
    d = repo_root / "environments" / "python"
    d.mkdir(parents=True, exist_ok=True)
    (d / "python-version").write_text(text, encoding="utf-8")


def pv():
    return platform.python_version()


def mm():
    return "%d.%d" % sys.version_info[:2]


def test_pin_major_minor_matches(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    write_pin(tmp_path, mm() + "\n")
    result = kind_python.provision(tmp_path)
    assert field(result, "ok") is True
    assert field(result, "reason") == ""
    assert field(result, "interpreter") == sys.executable
    assert field(result, "lockfile_sha256") is None


def test_pin_full_version_matches(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    write_pin(tmp_path, pv())
    result = kind_python.provision(tmp_path)
    assert field(result, "ok") is True
    assert field(result, "reason") == ""
    assert field(result, "interpreter") == sys.executable
    assert field(result, "lockfile_sha256") is None


def test_text_prefix_is_not_version_prefix(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    assert pv().startswith("3.1")
    assert not pv().startswith("3.1.")
    write_pin(tmp_path, "3.1\n")
    result = kind_python.provision(tmp_path)
    assert as_dict(result) == {
        "ok": False,
        "reason": "python environment: needs Python 3.1, found " + pv(),
        "versions": {},
        "lockfile_sha256": None,
        "interpreter": None,
    }


def test_pin_mismatch_with_lock_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    write_pin(tmp_path, "2.7")
    lock = tmp_path / "environments" / "python" / "requirements.lock"
    lock.write_text("--no-index\npytest==8.0.0\n", encoding="utf-8")
    lock_bytes = lock.read_bytes()
    result = kind_python.provision(tmp_path)
    assert as_dict(result) == {
        "ok": False,
        "reason": "python environment: needs Python 2.7, found " + pv(),
        "versions": {},
        "interpreter": None,
        "lockfile_sha256": "sha256:" + hashlib.sha256(lock_bytes).hexdigest(),
    }
    assert not (tmp_path / ".hotdocs").exists()