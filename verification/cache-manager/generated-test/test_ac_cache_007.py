import os
import shutil
import tempfile
import unittest
from pathlib import Path

import cache_manager


class TestAcCache007(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp())
        self._orig_store_url = os.environ.pop("VAR_CACHE_STORE_URL", None)

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)
        if self._orig_store_url is not None:
            os.environ["VAR_CACHE_STORE_URL"] = self._orig_store_url

    def test_payload_shape_mismatch_rejected_and_not_stored(self):
        cache_key = cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "a" * 64,
            gate_inputs_hash="sha256:" + "b" * 64,
            gate_version="license_scanner@4.0.3+9f2c41ab07de",
            model_pin="claude-sonnet-5",
        )

        # gate_type correctly declares "license_scanner" (matching the
        # cache_key's gate_version), but the payload is shaped like a
        # LintReport, missing license_scanner's required keys
        # (component_id, gate_version, similarity_score, blocked, matches).
        mismatched_result = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload={
                "errors": [],
                "warnings": [],
                "lines_checked": 42,
            },
            stored_at=cache_manager.now_iso(),
        )

        with self.assertRaises(cache_manager.SchemaValidationError):
            cache_manager.put(
                cache_key, mismatched_result, repo_root=self.repo_root
            )

        # Nothing was stored: a subsequent get for the same key is a miss.
        lookup_result = cache_manager.get(cache_key, repo_root=self.repo_root)
        self.assertIsInstance(lookup_result, cache_manager.Miss)

        stats_result = cache_manager.stats(repo_root=self.repo_root)
        entry_count = (
            stats_result.get("entry_count")
            if isinstance(stats_result, dict)
            else getattr(stats_result, "entry_count", None)
        )
        self.assertEqual(entry_count, 0)


if __name__ == "__main__":
    unittest.main()