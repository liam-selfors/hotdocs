import contextlib
import io
import json
import tempfile
from pathlib import Path

import cache_manager


def _run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cache_manager.main(argv)
    return exit_code, buf.getvalue()


def _parse_last_json_line(output):
    line = output.strip().splitlines()[-1]
    return json.loads(line)


def _entry_count(parsed):
    return parsed.get("entry_count") if isinstance(parsed, dict) else getattr(parsed, "entry_count", None)


def test_stats_on_empty_repo_root_reports_zero_entries():
    with tempfile.TemporaryDirectory() as repo_root:
        exit_code, output = _run_main(["stats", f"--repo-root={repo_root}"])

        assert exit_code == 0
        parsed = _parse_last_json_line(output)
        assert _entry_count(parsed) == 0


def test_stats_counts_distinct_keys_not_total_puts():
    with tempfile.TemporaryDirectory() as repo_root_str:
        repo_root = Path(repo_root_str)

        key_a = cache_manager.CacheKey(
            spec_bundle_hash="sha256:aaaa",
            gate_inputs_hash="sha256:1111",
            gate_version="license_scanner@1.0.0",
            model_pin="claude-sonnet-5",
        )
        key_b = cache_manager.CacheKey(
            spec_bundle_hash="sha256:bbbb",
            gate_inputs_hash="sha256:2222",
            gate_version="license_scanner@1.0.0",
            model_pin="claude-sonnet-5",
        )

        result_a = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload={
                "component_id": "comp-foo",
                "gate_version": "license_scanner@1.0.0",
                "similarity_score": 0.0,
                "blocked": False,
                "matches": [],
            },
            stored_at=cache_manager.now_iso(),
        )
        result_b = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload={
                "component_id": "comp-bar",
                "gate_version": "license_scanner@1.0.0",
                "similarity_score": 0.0,
                "blocked": False,
                "matches": [],
            },
            stored_at=cache_manager.now_iso(),
        )

        cache_manager.put(key_a, result_a, repo_root=repo_root)
        cache_manager.put(key_a, result_a, repo_root=repo_root)
        cache_manager.put(key_b, result_b, repo_root=repo_root)

        exit_code, output = _run_main(["stats", "--repo-root", str(repo_root)])

        assert exit_code == 0
        parsed = _parse_last_json_line(output)
        assert _entry_count(parsed) == 2