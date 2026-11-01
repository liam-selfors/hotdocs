import json
import subprocess

import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_pattern_db(path, rules=None, version="2.0.0"):
    if rules is None:
        rules = [
            {"rule_id": "aws-access-key-id", "risk_tier": "high",
             "pattern": "AKIA[0-9A-Z]{16}"},
        ]
    path.write_text(json.dumps({"version": version, "rules": rules}))


def _make_scan_dirs(repo_root):
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "gen").mkdir()
    (repo_root / "verification").mkdir()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VAR_SECRET_PATTERNS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    yield


def test_full_scan_clean_returns_zero_json(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    _make_scan_dirs(repo_root)
    (repo_root / "gen" / "app.py").write_text(
        "print('hello world, nothing secret here')\n"
    )

    pattern_db = tmp_path / "patterns.json"
    _write_pattern_db(pattern_db)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(pattern_db))

    rc = secret_scanner.main([f"--repo-root={repo_root}", "--format=json"])

    out = capsys.readouterr().out
    result = json.loads(out)
    assert rc == 0
    assert _get(result, "flagged") is False


def test_full_scan_flagged_returns_one_text(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    _make_scan_dirs(repo_root)
    (repo_root / "gen" / "config.py").write_text(
        "AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
    )

    pattern_db = tmp_path / "patterns.json"
    _write_pattern_db(pattern_db)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(pattern_db))

    rc = secret_scanner.main(["--repo-root", str(repo_root), "--format", "text"])

    out = capsys.readouterr().out
    assert rc == 1
    assert "FLAGGED" in out


def test_precommit_files_flagged_then_clean(tmp_path, monkeypatch, capsys):
    pattern_db = tmp_path / "patterns.json"
    _write_pattern_db(pattern_db)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(pattern_db))

    clean_file = tmp_path / "clean.py"
    clean_file.write_text("print('all good here')\n")
    secret_file = tmp_path / "secret.py"
    secret_file.write_text("KEY = 'AKIAABCDEFGHIJKLMNOP'\n")

    rc_flagged = secret_scanner.main(
        ["precommit", "--files", str(clean_file), f"--files={secret_file}"]
    )
    capsys.readouterr()
    assert rc_flagged == 1

    rc_clean = secret_scanner.main(["precommit", f"--files={clean_file}"])
    capsys.readouterr()
    assert rc_clean == 0


def test_precommit_git_default_files_flagged(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    git_env = {
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }

    def run_git(*args):
        subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            env=git_env,
        )

    run_git("init")
    clean_file = repo_root / "clean.py"
    clean_file.write_text("print('all good here')\n")
    run_git("add", "clean.py")
    run_git("commit", "-m", "init")

    secret_file = repo_root / "secret.py"
    secret_file.write_text("KEY = 'AKIAABCDEFGHIJKLMNOP'\n")
    run_git("add", "secret.py")

    pattern_db = tmp_path / "patterns.json"
    _write_pattern_db(pattern_db)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(pattern_db))

    rc = secret_scanner.main(["precommit", "--repo-root", str(repo_root)])

    assert rc == 1


def test_full_scan_skips_rule_missing_risk_tier(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    _make_scan_dirs(repo_root)
    (repo_root / "gen" / "config.py").write_text(
        "AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
    )

    pattern_db = tmp_path / "patterns.json"
    _write_pattern_db(
        pattern_db,
        rules=[
            {"rule_id": "bad-rule", "pattern": "AKIA[0-9A-Z]{16}"},
            {"rule_id": "aws-access-key-id", "risk_tier": "high",
             "pattern": "AKIA[0-9A-Z]{16}"},
        ],
        version="3.0.0",
    )
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(pattern_db))

    rc = secret_scanner.main([f"--repo-root={repo_root}", "--format=json"])

    out = capsys.readouterr().out
    result = json.loads(out)
    assert rc == 1
    matches = _get(result, "matches")
    rule_ids = {_get(m, "rule_id") for m in matches}
    assert rule_ids == {"aws-access-key-id"}


@pytest.mark.parametrize("extra_args", [["--format=bogus"], ["--unknown-flag=1"]])
def test_usage_error_variants_with_repo_root(tmp_path, extra_args):
    repo_root = tmp_path / "repo"
    _make_scan_dirs(repo_root)

    argv = [f"--repo-root={repo_root}", *extra_args]
    rc = secret_scanner.main(argv)

    assert rc == 2


def test_usage_error_unknown_subcommand():
    rc = secret_scanner.main(["bogus-subcommand"])
    assert rc == 2


def test_usage_error_repo_root_missing_value():
    rc = secret_scanner.main(["--repo-root"])
    assert rc == 2