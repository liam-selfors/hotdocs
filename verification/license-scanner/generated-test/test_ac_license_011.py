import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r'""".*?"""', "", text, flags=re.DOTALL)
    text = re.sub(r"'''.*?'''", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"#[^\n]*", "", text)
    return text


def _tokenize(text):
    return [t.lower() for t in TOKEN_RE.findall(_strip_comments(text))]


def _window_hashes(text):
    tokens = _tokenize(text)
    hashes = set()
    for i in range(len(tokens) - 8):
        window = tokens[i:i + 9]
        joined = "\x1f".join(window)
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


SOURCE_TEXT = (
    "def calculate_total_price(base_amount, tax_rate_percent, discount_value):\n"
    "    adjusted_amount = base_amount * tax_rate_percent\n"
    "    final_price_value = adjusted_amount - discount_value\n"
    "    return final_price_value\n"
    "\n"
    "def apply_discount_schedule(original_price, discount_schedule_id, customer_tier_level):\n"
    "    computed_discount_amount = original_price * discount_schedule_id\n"
    "    return computed_discount_amount - customer_tier_level\n"
)


def _write_component_source(repo_root):
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True, exist_ok=True)
    (foo_dir / "app.py").write_text(SOURCE_TEXT, encoding="utf-8")


def _write_corpus(repo_root, filename, hashes, block_threshold=0.70):
    corpus = {
        "corpus_version": 3,
        "block_threshold": block_threshold,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": sorted(hashes),
            }
        ],
    }
    corpus_path = repo_root / filename
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    return corpus_path


@pytest.fixture(autouse=True)
def _clean_webhook_env(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)


def test_clean_scan_reports_not_blocked_in_json_and_text(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "clean_repo"
    repo_root.mkdir()
    _write_component_source(repo_root)

    non_matching_hashes = {"f" * 64, "e" * 64}
    corpus_path = _write_corpus(repo_root, "corpus.json", non_matching_hashes)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    exit_code = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=json"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    result = json.loads(captured.out.strip())
    assert result["blocked"] is False

    exit_code_text = license_scanner.main(
        ["comp-foo", "--repo-root", str(repo_root), "--format", "text"]
    )
    captured_text = capsys.readouterr()
    assert exit_code_text == 0
    assert "similarity_score" in captured_text.out


def test_verbatim_copy_at_or_above_threshold_blocks(tmp_path, monkeypatch):
    repo_root = tmp_path / "blocked_repo"
    repo_root.mkdir()
    _write_component_source(repo_root)

    matching_hashes = _window_hashes(SOURCE_TEXT)
    assert matching_hashes, "fixture source text must produce at least one window"

    corpus_path = _write_corpus(repo_root, "corpus.json", matching_hashes)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    exit_code = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=json"]
    )
    assert exit_code == 1


def test_usage_errors_return_2(tmp_path, monkeypatch):
    repo_root = tmp_path / "usage_repo"
    repo_root.mkdir()

    bad_argvs = [
        # missing <component-id>
        [f"--repo-root={repo_root}", "--format=json"],
        # invalid --format value
        ["comp-foo", f"--repo-root={repo_root}", "--format=bogus"],
        # unknown argument
        ["comp-foo", f"--repo-root={repo_root}", "--totally-unknown-flag"],
        # --repo-root given last with no value
        ["comp-foo", "--repo-root"],
    ]

    for argv in bad_argvs:
        exit_code = license_scanner.main(argv)
        assert exit_code == 2, f"expected usage error (2) for argv={argv!r}, got {exit_code!r}"