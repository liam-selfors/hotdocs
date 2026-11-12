import hashlib
import io
import json
import os
import re
import sys
import textwrap
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-sample"
COMPONENT_SLUG = "sample"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return text


def _tokens(text):
    stripped = _strip_comments(text)
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", stripped)]


def _window_hashes(text):
    toks = _tokens(text)
    out = []
    for i in range(len(toks) - 9 + 1):
        window = "\x1f".join(toks[i:i + 9])
        out.append(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return out


def _source_text():
    # 18 distinct identifier tokens, no comments or string blocks -> 10
    # distinct 9-token windows.
    names = ["v%02d_ident" % i for i in range(18)]
    lines = []
    for i in range(0, len(names), 2):
        lines.append("%s = %s" % (names[i], names[i + 1]))
    return "\n".join(lines) + "\n"


FAKE_CACHE_MANAGER = textwrap.dedent(
    '''
    import json
    from dataclasses import dataclass, asdict
    from datetime import datetime, timezone

    _LOG_PATH = __LOG_PATH__

    _KNOWN = {
        "generator": ["component_id", "model", "prompt_version", "files"],
        "compiler": ["outputs", "gate_version", "summary"],
        "generated_test": ["component_id", "criterion_id", "model", "file"],
        "llm_judge": ["result", "rationale"],
        "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
        "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
    }


    def _log(record):
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\\n")


    class SchemaValidationError(ValueError):
        pass


    class Miss:
        def __eq__(self, other):
            return isinstance(other, Miss)

        def __hash__(self):
            return 0


    @dataclass
    class CacheKey:
        spec_bundle_hash: str
        gate_inputs_hash: str
        gate_version: str
        model_pin: str


    @dataclass
    class CachedResult:
        gate_type: str
        payload: dict
        stored_at: str


    def now_iso():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def get(cache_key, *, repo_root=None):
        _log({"call": "get", "gate_version": getattr(cache_key, "gate_version", None)})
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        gate_type = str(cache_key.gate_version).split("@", 1)[0]
        if result.gate_type != gate_type or gate_type not in _KNOWN:
            raise SchemaValidationError("gate_type mismatch")
        payload = result.payload if isinstance(result.payload, dict) else {}
        for key in _KNOWN[gate_type]:
            if key not in payload:
                raise SchemaValidationError("missing payload key: " + key)
        _log({"call": "put", "gate_version": cache_key.gate_version})
        return None


    def stats(*, repo_root=None):
        return {"entry_count": 0}


    def main(argv=None):
        return 0
    '''
)


def _build_repo(tmp_path, corpus_obj):
    root = tmp_path / "repo"
    comp_dir = root / "gen" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "sample.py").write_text(_source_text(), encoding="utf-8")

    log_path = tmp_path / "cache_calls.log"
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER.replace("__LOG_PATH__", repr(str(log_path))),
        encoding="utf-8",
    )

    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    corpus_path = corpus_dir / "reference.json"
    corpus_path.write_text(json.dumps(corpus_obj), encoding="utf-8")
    return root, corpus_path


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


def _filler_hashes(n):
    return [hashlib.sha256(("filler-%d" % i).encode("utf-8")).hexdigest() for i in range(n)]


def _run_cli(root, capsys):
    capsys.readouterr()
    try:
        rc = license_scanner.main([COMPONENT_ID, "--repo-root", str(root), "--format=json"])
    except SystemExit as exc:
        rc = exc.code
    out = capsys.readouterr().out
    return rc, out


def test_full_copy_above_default_threshold_blocks(clean_env, tmp_path, capsys):
    hashes = _window_hashes(_source_text())
    assert len(set(hashes)) == 10
    corpus = {
        "corpus_version": 3,
        "entries": [
            {
                "reference_id": "ref-copy",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": sorted(set(hashes)) + _filler_hashes(5),
            }
        ],
    }
    root, corpus_path = _build_repo(tmp_path, corpus)
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan(COMPONENT_ID, root)

    assert _field(result, "evaluated") is True
    score = _field(result, "similarity_score")
    threshold = _field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert abs(float(threshold) - 0.70) < 1e-9
    assert abs(float(score) - 1.0) < 1e-9
    assert float(score) >= float(threshold)
    assert _field(result, "blocked") is True

    rc, out = _run_cli(root, capsys)
    assert rc == 1
    payload = json.loads(out)
    assert payload.get("blocked") is True
    assert payload.get("evaluated") is True


def test_score_exactly_at_threshold_blocks(clean_env, tmp_path, capsys):
    hashes = _window_hashes(_source_text())
    distinct = list(dict.fromkeys(hashes))
    assert len(distinct) == 10
    # Half the component's distinct windows match -> score exactly 0.5.
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.5,
        "entries": [
            {
                "reference_id": "ref-half",
                "license_family": "Apache-2.0",
                "risk_tier": "low",
                "hashes": distinct[:5] + _filler_hashes(20),
            }
        ],
    }
    root, corpus_path = _build_repo(tmp_path, corpus)
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan(COMPONENT_ID, root)

    assert _field(result, "evaluated") is True
    score = _field(result, "similarity_score")
    threshold = _field(result, "block_threshold")
    assert abs(float(threshold) - 0.5) < 1e-9
    assert abs(float(score) - 0.5) < 1e-9
    assert _field(result, "blocked") is True

    matches = _field(result, "matches")
    assert matches, "a flagged (blocked) result must carry its matches"

    rc, out = _run_cli(root, capsys)
    assert rc == 1
    payload = json.loads(out)
    assert payload.get("blocked") is True


def test_blocked_text_output_reports_blocked(clean_env, tmp_path, capsys):
    hashes = _window_hashes(_source_text())
    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-copy",
                "license_family": "BSD",
                "risk_tier": "medium",
                "hashes": sorted(set(hashes)),
            }
        ],
    }
    root, corpus_path = _build_repo(tmp_path, corpus)
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    capsys.readouterr()
    try:
        rc = license_scanner.main([COMPONENT_ID, "--repo-root=" + str(root)])
    except SystemExit as exc:
        rc = exc.code
    out = capsys.readouterr().out
    assert rc == 1
    assert "blocked" in out.lower()
    assert "NOT EVALUATED" not in out