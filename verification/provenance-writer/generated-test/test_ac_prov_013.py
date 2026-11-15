import json
from pathlib import Path

import pytest

import provenance_writer


class _AttrDict(dict):
    """A plain dict that also supports attribute access and to_dict(),
    so it reads as either a JSON-shaped dict or a dataclass-like object."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self):
        return json.loads(json.dumps(self))


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return _AttrDict(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        model="claude-sonnet-5",
        prompt_version="v10",
        cache_hit=False,
        files={"foo_module.py": "def bar(x):\n    return x\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=None,
    )


def _verification_report():
    return _AttrDict(
        component_id="comp-foo",
        criteria=[
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )


def _license_scan_result():
    return _AttrDict(
        component_id="comp-foo",
        gate_version="license_scanner@4.0.0-no-reference-corpus",
        evaluated=False,
        reason="no-reference-corpus",
        similarity_score=None,
        block_threshold=None,
        blocked=False,
        matches=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def _secret_scan_result():
    return _AttrDict(
        scope="full",
        gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def _make_inputs():
    fields = dict(
        component_id="comp-foo",
        generation_result=_generation_result(),
        verification_report=_verification_report(),
        license_scan_result=_license_scan_result(),
        secret_scan_result=_secret_scan_result(),
        provenance_hit=False,
        attempts=2,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and callable(cls):
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


def _manifest_paths(repo_root: Path):
    return [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]


def _run(repo_root: Path, inputs):
    repo_root.mkdir(parents=True, exist_ok=True)
    provenance_writer.write_provenance("comp-foo", inputs, repo_root)
    manifests = []
    for path in _manifest_paths(repo_root):
        assert path.is_file(), f"expected manifest at {path}"
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def test_ac_prov_013_verification_run_id_is_deterministic(tmp_path):
    inputs = _make_inputs()

    # First run: verification_run_id is "<slug>-attempt-<attempts>".
    first = _run(tmp_path / "run1", inputs)
    for manifest in first:
        assert _field(manifest, "verification_run_id") == "foo-attempt-2"

    # Second run with the exact same inputs: identical verification_run_id.
    second = _run(tmp_path / "run2", inputs)
    for a, b in zip(first, second):
        assert _field(a, "verification_run_id") == _field(b, "verification_run_id")
        assert _field(b, "verification_run_id") == "foo-attempt-2"

    # Re-running into the same repo_root also yields the same id.
    third = _run(tmp_path / "run1", inputs)
    for a, c in zip(first, third):
        assert _field(a, "verification_run_id") == _field(c, "verification_run_id")