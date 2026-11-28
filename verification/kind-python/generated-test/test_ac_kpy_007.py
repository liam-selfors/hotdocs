# hotdocs-criterion: sha256:13a20462744c7135fc9e323a56e0312038335d4d0fac31cffcd87f2808c3e1be
import hashlib

import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_lock(tmp_path, text):
    lock = tmp_path / "environments" / "python" / "requirements.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(text, encoding="utf-8")
    return lock


def test_lock_without_pytest_pin_fails_before_anything_is_created(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    lock = _write_lock(
        tmp_path,
        "# pytest==8.3.0\npytest-cov==5.0.0\n-r other.txt\npytester\n",
    )
    expected_sha = "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest()

    result = kind_python.provision(tmp_path)

    assert isinstance(result, dict)
    assert result == {
        "ok": False,
        "reason": "python environment: requirements.lock does not pin pytest",
        "versions": {},
        "interpreter": None,
        "lockfile_sha256": expected_sha,
    }
    assert not (tmp_path / ".hotdocs").exists()


def test_hotdocs_regular_file_makes_lock_directory_creation_fail(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    (tmp_path / ".hotdocs").write_text("", encoding="utf-8")
    _write_lock(tmp_path, "--no-index\npytest==99.0.0\n")

    result = kind_python.provision(tmp_path)

    assert field(result, "ok") is False
    assert field(result, "versions") == {}
    assert field(result, "interpreter") is None
    reason = field(result, "reason")
    assert isinstance(reason, str)
    assert reason.startswith("python environment: [Errno 20] Not a directory: "), reason
    assert (tmp_path / ".hotdocs").is_file()