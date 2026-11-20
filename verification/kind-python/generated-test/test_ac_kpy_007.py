# hotdocs-criterion: sha256:a90596d708b800cd99a100e5abf4d51f095fb9e42be976711db9d04597aaac27
import hashlib
from pathlib import Path

import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_lock(repo_root: Path, text: str) -> bytes:
    lock_dir = repo_root / "environments" / "python"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = lock_dir / "requirements.lock"
    data = text.encode("utf-8")
    lock.write_bytes(data)
    return data


def test_lock_without_pytest_pin_fails_before_anything_is_created(tmp_path):
    data = _write_lock(
        tmp_path,
        "# pytest==8.3.0\npytest-cov==5.0.0\n-r other.txt\npytester\n",
    )

    result = kind_python.provision(tmp_path)

    expected = {
        "ok": False,
        "reason": "python environment: requirements.lock does not pin pytest",
        "versions": {},
        "interpreter": None,
        "lockfile_sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
    }
    if isinstance(result, dict):
        assert result == expected
    else:
        for key, value in expected.items():
            assert field(result, key) == value
    assert not (tmp_path / ".hotdocs").exists()


def test_hotdocs_as_regular_file_fails_with_not_a_directory(tmp_path):
    (tmp_path / ".hotdocs").write_bytes(b"")
    _write_lock(tmp_path, "--no-index\npytest==99.0.0\n")

    result = kind_python.provision(tmp_path)

    assert field(result, "ok") is False
    assert field(result, "versions") == {}
    assert field(result, "interpreter") is None
    reason = field(result, "reason")
    assert isinstance(reason, str)
    assert reason.startswith("python environment: [Errno 20] Not a directory: "), reason