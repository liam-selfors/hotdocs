import contextlib
import io
import json

import cache_manager


def _run(argv):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cache_manager.main(argv)
    return code, stdout.getvalue()


def test_inspect_hit_miss_and_usage_errors(tmp_path):
    repo_root = tmp_path

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash="sha256:a",
        gate_inputs_hash="sha256:b",
        gate_version="generator@1.0.0",
        model_pin="m",
    )
    cached_result = cache_manager.CachedResult(
        gate_type="generator",
        payload={
            "component_id": "comp-example",
            "model": "anthropic:claude-sonnet-5",
            "prompt_version": "1",
            "files": [],
        },
        stored_at="2026-01-01T00:00:00Z",
    )
    cache_manager.put(cache_key, cached_result, repo_root=repo_root)

    code, out = _run(
        [
            "inspect",
            "--spec-bundle-hash=sha256:a",
            "--gate-inputs-hash=sha256:b",
            "--gate-version=generator@1.0.0",
            "--model-pin=m",
            f"--repo-root={repo_root}",
        ]
    )
    assert code == 0
    parsed = json.loads(out.strip())
    assert parsed.get("result") == "hit"
    assert parsed.get("gate_type") == "generator"
    assert parsed.get("stored_at") == "2026-01-01T00:00:00Z"
    assert "payload" not in parsed

    code, out = _run(
        [
            "inspect",
            "--spec-bundle-hash=sha256:a",
            "--gate-inputs-hash=sha256:b",
            "--gate-version=generator@1.0.0",
            "--model-pin=other",
            f"--repo-root={repo_root}",
        ]
    )
    assert code == 0
    parsed = json.loads(out.strip())
    assert parsed.get("result") == "miss"

    code, _ = _run(["inspect", "--spec-bundle-hash=sha256:a"])
    assert code == 2

    code, _ = _run([])
    assert code == 2

    code, _ = _run(["purge"])
    assert code == 2