import contextlib
import io
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

import secret_scanner

AWS_KEY = "AKIAABCDEFGHIJKLMNOP"


@pytest.fixture(autouse=True)
def _no_webhook(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)


def _run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = secret_scanner.main(argv)
    return code, buf.getvalue()


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-C", str(repo_root)] + list(args),
        check=True,
        capture_output=True,
    )


def test_clean_repo_full_scan_json():
    with tempfile.TemporaryDirectory() as repo_root:
        repo_root = Path(repo_root)
        (repo_root / "README.md").write_text("hello world\n")
        code, out = _run(["--repo-root=" + str(repo_root), "--format=json"])
        assert code == 0
        result = json.loads(out)
        assert result["flagged"] is False


def test_secret_full_scan_text():
    with tempfile.TemporaryDirectory() as repo_root:
        repo_root = Path(repo_root)
        gen_dir = repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True)
        (gen_dir / "c.py").write_text('K = "%s"\n' % AWS_KEY)
        code, out = _run(["--repo-root", str(repo_root), "--format", "text"])
        assert code == 1
        assert "FLAGGED" in out


def test_precommit_files_repeated():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clean = tmp / "clean.py"
        clean.write_text("x = 1\n")
        secret = tmp / "secret.py"
        secret.write_text('K = "%s"\n' % AWS_KEY)

        code_flagged, _ = _run(
            ["precommit", "--files", str(clean), "--files=" + str(secret)]
        )
        assert code_flagged == 1

        code_clean, _ = _run(["precommit", "--files=" + str(clean)])
        assert code_clean == 0


def test_precommit_git_staged_defaults_to_flagged():
    with tempfile.TemporaryDirectory() as repo_root:
        repo_root = Path(repo_root)
        _git(repo_root, "init")
        _git(repo_root, "config", "user.email", "test@example.com")
        _git(repo_root, "config", "user.name", "Test")
        _git(repo_root, "config", "commit.gpgsign", "false")

        clean = repo_root / "clean.py"
        clean.write_text("x = 1\n")
        _git(repo_root, "add", "clean.py")
        _git(repo_root, "commit", "-m", "initial")

        secret = repo_root / "secret.py"
        secret.write_text('K = "%s"\n' % AWS_KEY)
        _git(repo_root, "add", "secret.py")

        code, _ = _run(["precommit", "--repo-root", str(repo_root)])
        assert code == 1


@pytest.mark.parametrize(
    "argv",
    [
        ["--format=bogus"],
        ["--banana=unknown"],
        ["frobnicate"],
        ["--repo-root"],
        ["propose", "--format=json"],
    ],
)
def test_usage_errors_exit_2(argv):
    code, _ = _run(argv)
    assert code == 2