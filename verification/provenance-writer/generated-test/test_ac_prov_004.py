"""AC-PROV-004 (Covers: R-PROV-004).

Given ProvenanceInputs with provenance_hit true
When write_provenance runs
Then the manifest's provenance_hit is true
"""
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


class _Rec(dict):
    """A plain dict that also reads as an object and offers to_dict().

    The documented upstream results are dataclasses with attribute access and
    (for some) a to_dict(); a plain JSON-shaped dict is also plausible. This
    stand-in satisfies either style of reading while remaining
    JSON-serializable.
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self):
        return json.loads(json.dumps(self))


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    # Every gate-level cache flag is false: provenance_hit must come only from
    # the caller's own ProvenanceInputs field, never inferred from these.
    return _Rec(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "a" * 64,
        model="claude-sonnet-5",
        prompt_version="v10",
        cache_hit=False,
        files={"widget_maker.py": "def make_widget(x):\n    return x\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=None,
    )


def _verification_report():
    return _Rec(
        component_id=COMPONENT_ID,
        criteria=[
            {
                "id": "AC-WIDGET-MAKER-001",
                "covers": "R-WIDGET-MAKER-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        requirement_results={"R-WIDGET-MAKER-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )


def _license_scan_result():
    return _Rec(
        component_id=COMPONENT_ID,
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
    return _Rec(
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


def _input_fields():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": True,
        "attempts": 1,
        "gate_versions": {
            "generator": "generator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    }


def _build_inputs():
    fields = _input_fields()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and callable(cls):
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


def _read_manifest(path: Path):
    assert path.is_file(), f"expected manifest at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_ac_prov_004_provenance_hit_true_is_recorded(tmp_path):
    repo_root = tmp_path / "repo"
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "widget_maker.py").write_text(
        "def make_widget(x):\n    return x\n", encoding="utf-8"
    )
    (repo_root / "verification" / SLUG).mkdir(parents=True)

    inputs = _build_inputs()

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    gen_manifest = _read_manifest(repo_root / "gen" / SLUG / ".provenance.json")
    ver_manifest = _read_manifest(
        repo_root / "verification" / SLUG / ".provenance.json"
    )

    for manifest in (gen_manifest, ver_manifest):
        assert field(manifest, "provenance_hit") is True