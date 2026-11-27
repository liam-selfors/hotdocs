# hotdocs-criterion: sha256:891276666a5d8128100084dff6d7e25e3ad6d5b711f1e20741354f6270c51b4a
"""AC-LICENSE-003c: a match at or above the block threshold against a
reference entry with risk_tier "low", with VAR-COMPLIANCE-WEBHOOK-URL not
configured, yields blocked true and notified false."""

import hashlib
import io
import json
import re
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import license_scanner


COMPONENT_ID = "comp-foo"
SLUG = "foo"

SOURCE_TEXT = (
    "def compute(alpha, beta, gamma):\n"
    "    return alpha + beta + gamma + 12 * delta - epsilon + zeta\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 9 + 1):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


FAKE_CACHE_MANAGER = (
    "import json\n"
    "from dataclasses import dataclass\n"
    "from datetime import datetime, timezone\n"
    "\n"
    "LOG_PATH = " + "LOG_PATH_PLACEHOLDER" + "\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


def build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "gen" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(SOURCE_TEXT, encoding="utf-8")

    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    log_path = tmp_path / "cache_calls.log"
    source = FAKE_CACHE_MANAGER.replace(
        "LOG_PATH_PLACEHOLDER", repr(str(log_path))
    )
    (cache_dir / "cache_manager.py").write_text(source, encoding="utf-8")

    hashes = window_hashes(SOURCE_TEXT)
    assert hashes, "fixture must yield at least one 9-token window"
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-low-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": hashes,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    return repo_root, corpus_path


def configure_env(monkeypatch, corpus_path):
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_low_tier_block_without_webhook_is_blocked_not_notified(tmp_path, monkeypatch):
    repo_root, corpus_path = build_repo(tmp_path)
    configure_env(monkeypatch, corpus_path)
    monkeypatch.chdir(repo_root)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    threshold = field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert score >= threshold

    matches = field(result, "matches")
    for match in matches:
        assert field(match, "risk_tier") != "high"

    assert field(result, "blocked") is True
    assert field(result, "notified") is False


def test_low_tier_block_without_webhook_via_cli(tmp_path, monkeypatch):
    repo_root, corpus_path = build_repo(tmp_path)
    configure_env(monkeypatch, corpus_path)
    monkeypatch.chdir(repo_root)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = license_scanner.main(
            [COMPONENT_ID, "--repo-root=" + str(repo_root), "--format=json"]
        )

    assert code == 1
    doc = json.loads(out.getvalue())
    assert field(doc, "evaluated") is True
    assert field(doc, "blocked") is True
    assert field(doc, "notified") is False