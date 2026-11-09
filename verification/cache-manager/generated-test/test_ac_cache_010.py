import os
import tempfile
import shutil
import unittest
from pathlib import Path

import cache_manager


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


class TestAcCache010(unittest.TestCase):
    def setUp(self):
        self._prior_store_url = os.environ.pop("VAR_CACHE_STORE_URL", None)
        self.repo_root = Path(tempfile.mkdtemp())

    def tearDown(self):
        if self._prior_store_url is not None:
            os.environ["VAR_CACHE_STORE_URL"] = self._prior_store_url
        shutil.rmtree(self.repo_root, ignore_errors=True)

    def test_put_then_get_round_trips_via_local_hotdocs_cache(self):
        self.assertNotIn("VAR_CACHE_STORE_URL", os.environ)

        cache_key = cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "a" * 64,
            gate_inputs_hash="sha256:" + "b" * 64,
            gate_version="license_scanner@4.0.3+9f2c41ab07de",
            model_pin="claude-sonnet-5",
        )

        stored_at = cache_manager.now_iso()
        payload = {
            "component_id": "comp-cache-manager",
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "similarity_score": 0.01,
            "blocked": False,
            "matches": [],
        }
        result = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload=payload,
            stored_at=stored_at,
        )

        # No distinct code path is used for the local-fallback case: the
        # same call shapes are used as would be used with a store URL set.
        cache_manager.put(cache_key, result, repo_root=self.repo_root)

        hotdocs_cache_dir = self.repo_root / ".hotdocs" / "cache"
        self.assertTrue(
            hotdocs_cache_dir.is_dir(),
            "put() with VAR_CACHE_STORE_URL absent MUST create .hotdocs/cache/",
        )
        written_files = [p for p in hotdocs_cache_dir.rglob("*") if p.is_file()]
        self.assertGreater(
            len(written_files),
            0,
            "put() MUST persist at least one file under .hotdocs/cache/",
        )

        retrieved = cache_manager.get(cache_key, repo_root=self.repo_root)

        self.assertFalse(
            isinstance(retrieved, cache_manager.Miss),
            "get() for a key just put() MUST NOT report a miss",
        )
        self.assertEqual(_field(retrieved, "gate_type"), "license_scanner")
        self.assertEqual(_field(retrieved, "payload"), payload)
        self.assertEqual(_field(retrieved, "stored_at"), stored_at)

        # Confirm the value truly came back from disk, not merely from an
        # in-process cache: remove the on-disk store and verify the next
        # get() for the same key now reports a miss.
        shutil.rmtree(hotdocs_cache_dir)
        post_delete = cache_manager.get(cache_key, repo_root=self.repo_root)
        self.assertTrue(
            isinstance(post_delete, cache_manager.Miss),
            "with .hotdocs/cache/ removed, get() MUST report Miss, proving "
            "the prior hit was read back from that on-disk store",
        )


if __name__ == "__main__":
    unittest.main()