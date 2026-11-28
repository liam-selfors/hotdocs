# hotdocs-criterion: sha256:0cdffb20f5245c25a77025bdf3bf85420d765f0a0feb46426eb973f479888c55
"""AC-LICENSE-008: an 8-token shared run contributes no matching window-hash.

Covers R-LICENSE-001: the window size is exactly 9 tokens, not 8 or any
other nearby value.
"""

import hashlib
import json
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-widget"
SLUG = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def window_hash(tokens):
    return hashlib.sha256("\x1f".join(tokens).encode("utf-8")).hexdigest()


def all_windows(tokens, k):
    return [tokens[i:i + k] for i in range(len(tokens) - k + 1)]


def write_fake_cache_manager(repo_root, log_path):
    src = (
        "import dataclasses\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
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
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
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
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(src, encoding="utf-8")


def write_spec_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + SLUG + "/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "A fixture component.\n",
        encoding="utf-8",
    )
    (comp / "requirements" / "R-WIDGET-001.md").write_text(
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST exist.\n",
        encoding="utf-8",
    )
    (comp / "acceptance" / "AC-WIDGET-001.md").write_text(
        "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\n",
        encoding="utf-8",
    )


def build_repo(tmp_path, component_tokens, corpus_hashes):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    write_fake_cache_manager(repo_root, log_path)
    write_spec_fixture(repo_root)

    content = "\n".join(
        " ".join(component_tokens[i:i + 4])
        for i in range(0, len(component_tokens), 4)
    ) + "\n"
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "widget.py").write_text(content, encoding="utf-8")
    legacy_dir = repo_root / "legacy" / SLUG
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "widget.py").write_text(content, encoding="utf-8")

    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.01,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": sorted(set(corpus_hashes)),
            }
        ],
    }
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    return repo_root, corpus_path


SHARED = ["sa", "sb", "sc", "sd", "se", "sf", "sg", "sh"]
PREFIX = ["ua", "ub", "uc"]
SUFFIX = ["ud", "ue", "uf"]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_shared_8_token_run_contributes_no_matching_window_hash(tmp_path, monkeypatch):
    component_tokens = PREFIX + SHARED + SUFFIX

    # The reference entry "contains" the 8-token run: give it every hash a
    # window of any size other than 9 over that run would produce (and
    # nearby sizes over the component itself), but no 9-token run is shared.
    corpus_hashes = []
    for k in range(1, 9):
        for w in all_windows(SHARED, k):
            corpus_hashes.append(window_hash(w))
    for k in (7, 8, 10, 11):
        for w in all_windows(component_tokens, k):
            corpus_hashes.append(window_hash(w))
    # Sanity: none of the component's real 9-token windows is in the corpus.
    nine = {window_hash(w) for w in all_windows(component_tokens, 9)}
    assert not (nine & set(corpus_hashes))

    repo_root, corpus_path = build_repo(tmp_path, component_tokens, corpus_hashes)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    assert score is not None
    assert score == 0, "an 8-token shared run must contribute no matching window-hash"
    assert field(result, "blocked") is False
    for m in field(result, "matches"):
        assert field(m, "score") == 0


def test_shared_9_token_run_does_match_positive_control(tmp_path, monkeypatch):
    shared9 = SHARED + ["si"]
    component_tokens = PREFIX + shared9 + SUFFIX
    corpus_hashes = [window_hash(shared9)]

    repo_root, corpus_path = build_repo(tmp_path, component_tokens, corpus_hashes)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert field(result, "evaluated") is True
    distinct = {window_hash(w) for w in all_windows(component_tokens, 9)}
    expected = 1 / len(distinct)
    score = field(result, "similarity_score")
    assert score == pytest.approx(expected)
    assert field(result, "blocked") is True