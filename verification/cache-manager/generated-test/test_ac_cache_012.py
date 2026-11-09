import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import cache_manager


class TestACCache012(unittest.TestCase):
    def setUp(self):
        self._old_env = os.environ.get("VAR_CACHE_STORE_URL")
        os.environ["VAR_CACHE_STORE_URL"] = "redis://cache.internal:6379/0"
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = self._tmpdir.name

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("VAR_CACHE_STORE_URL", None)
        else:
            os.environ["VAR_CACHE_STORE_URL"] = self._old_env
        self._tmpdir.cleanup()

    def test_remote_store_url_forces_miss_and_empty_local_cache(self):
        cache_key = cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "a" * 64,
            gate_inputs_hash="sha256:" + "b" * 64,
            gate_version="license_scanner@4.0.3+9f2c41ab07de",
            model_pin="claude-sonnet-5",
        )
        result = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload={
                "component_id": "comp-foo",
                "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
                "similarity_score": 0.0,
                "blocked": False,
                "matches": [],
            },
            stored_at=cache_manager.now_iso(),
        )

        cache_manager.put(cache_key, result, repo_root=Path(self.repo_root))
        got = cache_manager.get(cache_key, repo_root=Path(self.repo_root))

        self.assertIsInstance(got, cache_manager.Miss)

        cache_dir = Path(self.repo_root) / ".hotdocs" / "cache"
        self.assertFalse(cache_dir.exists())

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = cache_manager.main(
                ["stats", "--repo-root=" + self.repo_root]
            )
        self.assertEqual(exit_code, 0)

        output = buf.getvalue().strip()
        parsed = json.loads(output)
        entry_count = (
            parsed.get("entry_count")
            if isinstance(parsed, dict)
            else getattr(parsed, "entry_count", None)
        )
        self.assertEqual(entry_count, 0)

    def test_put_still_validates_schema_with_remote_store_url_set(self):
        cache_key = cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "c" * 64,
            gate_inputs_hash="sha256:" + "d" * 64,
            gate_version="secret_scanner@1.0.0+deadbeef",
            model_pin="claude-sonnet-5",
        )
        invalid_result = cache_manager.CachedResult(
            gate_type="secret_scanner",
            payload={
                "scope": "repo",
                "gate_version": "secret_scanner@1.0.0+deadbeef",
                "flagged": False,
            },
            stored_at=cache_manager.now_iso(),
        )

        with self.assertRaises(cache_manager.SchemaValidationError):
            cache_manager.put(
                cache_key, invalid_result, repo_root=Path(self.repo_root)
            )


if __name__ == "__main__":
    unittest.main()