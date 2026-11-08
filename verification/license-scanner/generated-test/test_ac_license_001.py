import contextlib
import hashlib
import io
import json
import os
import tempfile
import textwrap
from pathlib import Path

import license_scanner


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


FAKE_CACHE_MANAGER_SOURCE = textwrap.dedent(
    """
    import dataclasses
    from typing import Any, Optional


    @dataclasses.dataclass
    class CacheKey:
        spec_bundle_hash: str
        gate_inputs_hash: str
        gate_version: str
        model_pin: str


    @dataclasses.dataclass
    class CachedResult:
        gate_type: str
        payload: Any
        stored_at: str


    @dataclasses.dataclass
    class Miss:
        payload: Optional[Any] = None


    def get(cache_key, *, repo_root=None):
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        return None
    """
)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    sample_dir = repo_root / "gen" / "sample"
    sample_dir.mkdir(parents=True)

    tokens = [
        "alpha", "beta", "gamma", "delta", "epsilon",
        "zeta", "eta", "theta", "iota",
    ]
    source_text = " ".join(tokens) + "\n"
    (sample_dir / "module.py").write_text(source_text, encoding="utf-8")

    window_hash = hashlib.sha256(
        "\x1f".join(tokens).encode("utf-8")
    ).hexdigest()

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8"
    )

    corpus_path = repo_root / "license_corpus.json"
    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.5,
        "entries": [
            {
                "reference_id": "ref-test-1",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": [window_hash],
            }
        ],
    }
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    return repo_root, corpus_path


def test_license_scan_blocks_when_similarity_at_or_above_threshold():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        repo_root, corpus_path = _build_repo(tmp_path)

        old_env = os.environ.get("VAR_LICENSE_CORPUS_PATH")
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
        try:
            result = license_scanner.scan("comp-sample", repo_root)

            evaluated = _field(result, "evaluated")
            similarity_score = _field(result, "similarity_score")
            block_threshold = _field(result, "block_threshold")
            blocked = _field(result, "blocked")

            assert evaluated is True
            assert similarity_score is not None
            assert block_threshold is not None
            assert similarity_score >= block_threshold
            assert blocked is True

            argv = [
                "comp-sample",
                "--repo-root=" + str(repo_root),
                "--format=json",
            ]
            stdout = io.StringIO()
            exit_code = None
            try:
                with contextlib.redirect_stdout(stdout):
                    returned = license_scanner.main(argv)
                exit_code = returned
            except SystemExit as exc:
                exit_code = exc.code

            assert exit_code == 1

            cli_result = json.loads(stdout.getvalue().strip())
            assert _field(cli_result, "blocked") is True
            assert _field(cli_result, "evaluated") is True
        finally:
            if old_env is None:
                os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
            else:
                os.environ["VAR_LICENSE_CORPUS_PATH"] = old_env