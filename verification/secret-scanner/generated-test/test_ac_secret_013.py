import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import secret_scanner


FAKE_CACHE_MANAGER_SRC = '''
class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None, gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


def get(cache_key, repo_root=None):
    return None


def put(cache_key, result, repo_root=None):
    pass
'''

AKIA_KEY_LINE = 'K = "AKIAABCDEFGHIJKLMNOP"\n'


def _write_fake_cache_manager(repo_root):
    cache_dir = Path(repo_root) / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SRC)


def _run_git(args, cwd):
    subprocess.run(["git"] + args, cwd=str(cwd), check=True, capture_output=True)


class TestACSecret013(unittest.TestCase):
    def setUp(self):
        self._saved_webhook_var = os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
        self.tmp = tempfile.mkdtemp()
        self.repo_root = Path(self.tmp) / "repo"
        self.repo_root.mkdir()
        _write_fake_cache_manager(self.repo_root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self._saved_webhook_var is not None:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = self._saved_webhook_var

    def test_full_scan_clean_repo_returns_0_and_json_not_flagged(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = secret_scanner.main(
                ["--repo-root=" + str(self.repo_root), "--format=json"]
            )
        self.assertEqual(code, 0)
        result = json.loads(buf.getvalue())
        flagged = result.get("flagged") if isinstance(result, dict) else getattr(result, "flagged", None)
        self.assertFalse(flagged)

    def test_full_scan_with_secret_returns_1_and_text_flagged(self):
        gen_foo = self.repo_root / "gen" / "foo"
        gen_foo.mkdir(parents=True, exist_ok=True)
        (gen_foo / "c.py").write_text(AKIA_KEY_LINE)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = secret_scanner.main(
                ["--repo-root", str(self.repo_root), "--format", "text"]
            )
        self.assertEqual(code, 1)
        self.assertIn("FLAGGED", buf.getvalue())

    def test_precommit_repeated_files_flag(self):
        clean_file = self.repo_root / "clean.py"
        clean_file.write_text("y = 2\n")
        secret_file = self.repo_root / "secret.py"
        secret_file.write_text(AKIA_KEY_LINE)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code_with_secret = secret_scanner.main(
                ["precommit", "--files", str(clean_file), "--files=" + str(secret_file)]
            )
        self.assertEqual(code_with_secret, 1)

        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            code_clean_only = secret_scanner.main(
                ["precommit", "--files=" + str(clean_file)]
            )
        self.assertEqual(code_clean_only, 0)

    def test_precommit_git_default_discovery_returns_1(self):
        git_repo = Path(self.tmp) / "gitrepo"
        git_repo.mkdir()
        _run_git(["init"], git_repo)

        clean_file = git_repo / "clean.py"
        clean_file.write_text("z = 3\n")
        _run_git(["add", "clean.py"], git_repo)
        _run_git(
            [
                "-c", "user.email=test@example.com",
                "-c", "user.name=Test",
                "commit", "-m", "init",
            ],
            git_repo,
        )

        secret_file = git_repo / "secret.py"
        secret_file.write_text(AKIA_KEY_LINE)
        _run_git(["add", "secret.py"], git_repo)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = secret_scanner.main(["precommit", "--repo-root", str(git_repo)])
        self.assertEqual(code, 1)

    def test_usage_errors_return_2(self):
        bad_argvs = [
            ["--format=bogus"],
            ["--this-flag-does-not-exist"],
            ["not-a-real-subcommand"],
            ["--repo-root"],
            ["propose", "--format=json"],
        ]
        for argv in bad_argvs:
            buf = io.StringIO()
            err = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                code = secret_scanner.main(list(argv))
            self.assertEqual(code, 2, "expected exit 2 for argv=%r" % (argv,))


if __name__ == "__main__":
    unittest.main()