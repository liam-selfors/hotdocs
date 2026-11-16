import dataclasses
import json
from pathlib import Path

import provenance_writer


class DualDict(dict):
    """A dict that also reads as an object (attribute access) and offers to_dict()."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def to_dict(self):
        return json.loads(json.dumps(self))


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return DualDict(
        {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo_widget.py": "def make_widget(x):\n    return x\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": ["R-FOO-002"],
        }
    )


def _verification_report():
    return DualDict(
        {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                },
                {
                    "id": "AC-FOO-002",
                    "covers": "R-FOO-002",
                    "kind": "compiled",
                    "result": "pass",
                },
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        }
    )


def _license_scan_result():
    return DualDict(
        {
            "component_id": "comp-foo",
            "gate_version": "license_scanner@4.0.0-no-reference-corpus",
            "evaluated": False,
            "reason": "no-reference-corpus",
            "similarity_score": None,
            "block_threshold": None,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }
    )


def _secret_scan_result():
    return DualDict(
        {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }
    )


def _build_inputs():
    data = {
        "component_id": "comp-foo",
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            pass
    return data


def _keys_anywhere(value):
    keys = set()
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            keys |= _keys_anywhere(v)
    elif isinstance(value, list):
        for item in value:
            keys |= _keys_anywhere(item)
    return keys


def test_ac_prov_002_generation_fields_copied_and_no_sample_index(tmp_path):
    repo_root = Path(tmp_path)
    (repo_root / "gen" / "foo").mkdir(parents=True, exist_ok=True)
    (repo_root / "verification" / "foo").mkdir(parents=True, exist_ok=True)

    inputs = _build_inputs()
    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    manifest_paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in manifest_paths:
        assert path.is_file(), f"manifest not written at {path}"
        text = path.read_text(encoding="utf-8")
        manifest = json.loads(text)
        assert isinstance(manifest, dict)

        assert field(manifest, "model_pin") == "claude-sonnet-5"
        assert field(manifest, "prompt_version") == "v1"
        assert field(manifest, "retry_feedback") == ["R-FOO-002"]

        assert "sample_index" not in _keys_anywhere(manifest), (
            f"sample_index field present in {path}"
        )
        assert "sample_index" not in text, f"sample_index appears in {path}"