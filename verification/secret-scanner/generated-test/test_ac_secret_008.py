import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


CACHE_MANAGER_SOURCE = '''
import os


def _log(event):
    log_path = os.environ.get("AC_SECRET_008_CACHE_LOG")
    if not log_path:
        return
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(event + "\\n")


_log("imported")


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                 gate_version=None, model_pin=None):
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
    _log("get")
    return None


def put(cache_key, cached_result, repo_root=None):
    _log("put")
    return None
'''

AWS_KEY_FIXTURE = "AKIA" + "IOSFODNN7" + "EXAMPLE"


class TestAcSecret008(unittest.TestCase):
    def setUp(self):
        import secret_scanner

        self.secret_scanner = secret_scanner

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = Path(self._tmp.name)

        (self.repo_root / "included.py").write_text(
            'included_secret = "%s"\n' % AWS_KEY_FIXTURE, encoding="utf-8"
        )
        (self.repo_root / "excluded.py").write_text(
            'excluded_secret = "%s"\n' % AWS_KEY_FIXTURE, encoding="utf-8"
        )

        cache_manager_dir = self.repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(
            CACHE_MANAGER_SOURCE, encoding="utf-8"
        )

        self.cache_log = self.repo_root / "cache_manager_calls.log"
        self._old_env = os.environ.get("AC_SECRET_008_CACHE_LOG")
        os.environ["AC_SECRET_008_CACHE_LOG"] = str(self.cache_log)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self._old_env is None:
            os.environ.pop("AC_SECRET_008_CACHE_LOG", None)
        else:
            os.environ["AC_SECRET_008_CACHE_LOG"] = self._old_env

    def _run_precommit(self, argv):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = self.secret_scanner.main(argv)
        return exit_code, stdout.getvalue()

    def test_precommit_scans_only_given_file_with_no_cache_lookup(self):
        argv = [
            "precommit",
            "--files=included.py",
            "--repo-root=%s" % str(self.repo_root),
            "--format=json",
        ]
        exit_code, output = self._run_precommit(argv)

        self.assertEqual(exit_code, 1)
        result = json.loads(output)

        self.assertEqual(_get(result, "scope"), "precommit")
        self.assertTrue(_get(result, "flagged"))
        self.assertEqual(_get(result, "cache_hit"), False)

        matches = _get(result, "matches") or []
        self.assertTrue(matches)
        files_matched = {_get(m, "file") for m in matches}
        self.assertIn("included.py", files_matched)
        self.assertNotIn("excluded.py", files_matched)

        for m in matches:
            self.assertEqual(_get(m, "file"), "included.py")

        self.assertFalse(
            self.cache_log.exists(),
            "cache-manager stand-in was invoked during a precommit scan, "
            "but R-SECRET-008 requires no cache-manager lookup",
        )

    def test_precommit_file_selection_excludes_other_repo_files(self):
        argv = [
            "precommit",
            "--files=excluded.py",
            "--repo-root=%s" % str(self.repo_root),
            "--format=json",
        ]
        exit_code, output = self._run_precommit(argv)

        self.assertEqual(exit_code, 1)
        result = json.loads(output)

        matches = _get(result, "matches") or []
        self.assertTrue(matches)
        files_matched = {_get(m, "file") for m in matches}
        self.assertIn("excluded.py", files_matched)
        self.assertNotIn("included.py", files_matched)

        self.assertFalse(
            self.cache_log.exists(),
            "cache-manager stand-in was invoked during a precommit scan, "
            "but R-SECRET-008 requires no cache-manager lookup",
        )


if __name__ == "__main__":
    unittest.main()