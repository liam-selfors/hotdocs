import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

import secret_scanner

AWS_KEY = "AKIAABCDEFGHIJKLMNOP"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = secret_scanner.main(argv)
    return code, buf.getvalue()


def _git(args, cwd):
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
    )


def test_full_scan_clean_returns_zero_with_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "clean.py").write_text("x = 1\n")

    code, out = _run_main(
        ["--repo-root=" + str(repo_root), "--format=json"]
    )

    assert code == 0
    data = json.loads(out[out.index("{"):])
    assert _get(data, "flagged") is False


def test_full_scan_flagged_returns_one_with_text(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "c.py").write_text(
        'K = "%s"\n' % AWS_KEY
    )

    code, out = _run_main(
        ["--repo-root", str(repo_root), "--format", "text"]
    )

    assert code == 1
    assert "FLAGGED" in out


def test_precommit_explicit_files(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("a = 1\n")
    secret = tmp_path / "secret.py"
    secret.write_text('K = "%s"\n' % AWS_KEY)

    code_with_secret, _ = _run_main(
        ["precommit", "--files", str(clean), "--files=" + str(secret)]
    )
    assert code_with_secret == 1

    code_clean_only, _ = _run_main(
        ["precommit", "--files", str(clean)]
    )
    assert code_clean_only == 0


def test_precommit_defaults_to_git_diff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _git(["init"], repo_root)
    _git(["config", "user.email", "test@example.com"], repo_root)
    _git(["config", "user.name", "Test User"], repo_root)

    (repo_root / "clean.py").write_text("a = 1\n")
    _git(["add", "clean.py"], repo_root)
    _git(["commit", "-m", "initial commit"], repo_root)

    (repo_root / "secret.py").write_text('K = "%s"\n' % AWS_KEY)
    _git(["add", "secret.py"], repo_root)

    code, _ = _run_main(["precommit", "--repo-root", str(repo_root)])

    assert code == 1


@pytest.mark.parametrize(
    "argv",
    [
        ["--format=bogus"],
        ["--totally-unknown-flag"],
        ["not-a-real-subcommand"],
        ["--repo-root"],
        ["propose", "--format=json"],
    ],
)
def test_usage_errors_return_two(argv):
    code, _ = _run_main(argv)
    assert code == 2