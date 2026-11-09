import os
import tempfile
import unittest
from pathlib import Path


class TestACCache001GetMissingKeyReturnsMiss(unittest.TestCase):
    def test_get_on_unstored_key_returns_definitive_miss(self):
        import cache_manager

        env_var = "VAR_CACHE_STORE_URL"
        had_env_var = env_var in os.environ
        saved_env_value = os.environ.get(env_var)
        if had_env_var:
            del os.environ[env_var]

        try:
            with tempfile.TemporaryDirectory() as repo_root_str:
                repo_root = Path(repo_root_str)

                cache_key = cache_manager.CacheKey(
                    spec_bundle_hash="sha256:" + "0" * 64,
                    gate_inputs_hash="sha256:" + "1" * 64,
                    gate_version="license_scanner@4.0.3+9f2c41ab07de",
                    model_pin="claude-sonnet-5",
                )

                result = cache_manager.get(cache_key, repo_root=repo_root)

                self.assertIsInstance(
                    result,
                    cache_manager.Miss,
                    "get() on a key with no stored entry must return a Miss instance",
                )
                self.assertNotIsInstance(
                    result,
                    Exception,
                    "get() must not return/raise an error for an unstored key",
                )

                other_result = cache_manager.get(cache_key, repo_root=repo_root)
                self.assertEqual(
                    result,
                    other_result,
                    "any two Miss instances must compare equal",
                )
        finally:
            if had_env_var:
                os.environ[env_var] = saved_env_value


if __name__ == "__main__":
    unittest.main()