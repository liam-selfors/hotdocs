# hotdocs-criterion: sha256:eae1989deaa1c7def6077fc5d3fbeabd372208751ca898a73c43fe1ca4b75288
import hashlib
import json
import re
import sys
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = (
    "def alpha_function(beta, gamma, delta):\n"
    "    epsilon = beta + gamma * 42\n"
    "    zeta = epsilon - delta / 7\n"
    "    for eta in range(10):\n"
    "        zeta = zeta + eta * theta_value\n"
    "    return zeta + iota_constant - kappa_offset\n"
)


def window_hashes(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        joined = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return sorted(hashes)


def write_fake_cache_manager(repo_root, log_path):
    src = (
        "import json\n"
        "from dataclasses import dataclass, asdict, is_dataclass\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _log(record):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(json.dumps(record, default=str) + '\\n')\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log({'call': 'get'})\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    payload = result.payload if hasattr(result, 'payload') else result['payload']\n"
        "    if is_dataclass(payload):\n"
        "        payload = asdict(payload)\n"
        "    gate_type = result.gate_type if hasattr(result, 'gate_type') else result['gate_type']\n"
        "    _log({'call': 'put', 'gate_type': gate_type, 'payload': payload})\n"
        "    return None\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
    )
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(src)


def test_low_risk_block_without_webhook_still_records(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(SOURCE)

    hashes = window_hashes(SOURCE)
    assert hashes

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
    corpus_path.write_text(json.dumps(corpus))

    log_path = tmp_path / "cache_log.jsonl"
    write_fake_cache_manager(repo_root, log_path)

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.chdir(repo_root)

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is True
    assert field(result, "similarity_score") >= field(result, "block_threshold")
    assert field(result, "blocked") is True
    assert field(result, "notified") is False
    assert field(result, "notification_delivery_error") is None

    matches = field(result, "matches")
    assert len(matches) >= 1
    assert all(field(m, "risk_tier") != "high" for m in matches)
    assert any(field(m, "reference_id") == "ref-low-001" for m in matches)
    assert field(result, "component_id") == "comp-foo"

    # The LicenseScanResult record is still produced and stored after the fresh scan.
    assert log_path.is_file()
    records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    puts = [r for r in records if r.get("call") == "put"]
    assert len(puts) >= 1
    payload = puts[-1]["payload"]
    assert puts[-1]["gate_type"] == "license_scanner"
    assert payload["component_id"] == "comp-foo"
    assert payload["blocked"] is True
    assert payload["notified"] is False