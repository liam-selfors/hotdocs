# hotdocs-criterion: sha256:b2c4d7fa535f3661573e0bcfcd5c43f480e0f23d94800dc5858c99b55929ddd1
import hashlib
import json
import re
import socket
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER = (
    "from dataclasses import dataclass\n"
    "from typing import Any\n"
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
    "    payload: Any\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    import datetime\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime("
    + repr("%Y-%m-%dT%H:%M:%SZ")
    + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {" + repr("entry_count") + ": 0}\n"
)


def _source_text():
    lines = []
    for i in range(40):
        lines.append(
            "value_" + str(i) + " = compute_" + str(i)
            + "(alpha_" + str(i) + ", beta_" + str(i) + ", gamma_" + str(i) + ")\n"
        )
    return "".join(lines)


def _window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = []
    seen = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        h = hashlib.sha256(window.encode("utf-8")).hexdigest()
        if h not in seen:
            seen.add(h)
            hashes.append(h)
    return hashes


def _closed_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _build_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    text = _source_text()

    # Component source, in both the generated and sealed locations.
    for d in (root / "gen" / "foo", root / "legacy" / "foo"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "foo.py").write_text(text, encoding="utf-8")

    comp_dir = root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n",
        encoding="utf-8",
    )
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST compute values.\n", encoding="utf-8"
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n", encoding="utf-8"
    )
    (comp_dir / "constraints.md").write_text("# Constraints\n", encoding="utf-8")

    # Fake cache-manager that always misses, so each scan is fresh.
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    # Corpus with a single high-risk entry matching ~80% of windows,
    # below a 0.9 block threshold.
    hashes = _window_hashes(text)
    keep = hashes[: int(len(hashes) * 0.8)]
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.9,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": keep,
            }
        ],
    }
    corpus_path = root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    return corpus_path


def test_ac_license_009_webhook_network_error_recorded_not_raised(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    # Control run: no webhook configured.
    control_root = tmp_path / "control"
    control_corpus = _build_repo(control_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(control_corpus))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    control = license_scanner.scan("comp-foo", control_root)
    assert field(control, "evaluated") is True
    control_matches = field(control, "matches")
    assert any(field(m, "risk_tier") == "high" for m in control_matches)
    control_blocked = field(control, "blocked")

    # Run with a webhook URL pointing at a closed local port -> network error.
    test_root = tmp_path / "subject"
    test_corpus = _build_repo(test_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(test_corpus))
    url = "http://127.0.0.1:" + str(_closed_port()) + "/hook"
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", url)

    result = license_scanner.scan("comp-foo", test_root)

    assert field(result, "evaluated") is True
    assert any(field(m, "risk_tier") == "high" for m in field(result, "matches"))
    assert field(result, "notified") is True

    err = field(result, "notification_delivery_error")
    assert err is not None
    assert field(err, "category") == "network"
    message = field(err, "message")
    assert isinstance(message, str)

    assert field(result, "blocked") == control_blocked
    assert field(result, "similarity_score") == field(control, "similarity_score")