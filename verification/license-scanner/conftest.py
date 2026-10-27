import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "license-scanner"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
import license_scanner  # noqa: E402


def write_gen_file(repo_root: Path, slug: str, filename: str, content: str) -> Path:
    gen_dir = repo_root / "gen" / slug
    gen_dir.mkdir(parents=True, exist_ok=True)
    path = gen_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def real_hashes_for(repo_root: Path, slug: str) -> set:
    """The scanner's own real k-gram hashes for whatever currently sits
    under gen/<slug>/ -- used to build a reference-corpus entry that is
    guaranteed to match (or partially match) without reimplementing the
    tokenizer/hashing algorithm by hand."""
    gen_dir = repo_root / "gen" / slug
    return license_scanner._document_kgram_hashes(gen_dir)


def write_corpus(repo_root: Path, entries: list, corpus_version=1, block_threshold=0.70) -> Path:
    corpus_path = repo_root / "reference-corpus.json"
    corpus_path.write_text(json.dumps({
        "corpus_version": corpus_version,
        "block_threshold": block_threshold,
        "entries": entries,
    }), encoding="utf-8")
    return corpus_path


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    return tmp_path
