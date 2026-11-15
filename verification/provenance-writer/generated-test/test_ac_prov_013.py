import json
from pathlib import Path

import provenance_writer


class _AttrDict(dict):
    """A plain dict that also allows attribute-style reads.

    Lets the faked upstream results be read either as a mapping or as an
    object, since the ProvenanceInputs contract describes them by their
    JSON shape only.
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    # A refused generation: no candidate files, so verification_report is
    # legitimately null (no missing upstream result).
    return _AttrDict(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "0" * 64,
        model="claude-sonnet-5",
        prompt_version="v1",
        cache_hit=False,
        files={},
        model_call_error=None,
        refused="sealed-component",
        retry_feedback=None,
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


def _input_fields():
    return dict(
        component_id="comp-foo",
        generation_result=_generation_result(),
        verification_report=None,
        license_scan_result=_license_scan_result(),
        secret_scan_result=_secret_scan_result(),
        provenance_hit=False,
        attempts=2,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def _make_inputs():
    fields = _input_fields()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


def _run(repo_root: Path, inputs):
    (repo_root / "gen" / "foo").mkdir(parents=True, exist_ok=True)
    (repo_root / "verification" / "foo").mkdir(parents=True, exist_ok=True)
    provenance_writer.write_provenance("comp-foo", inputs, repo_root)
    manifests = []
    for path in (
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ):
        assert path.is_file(), f"expected manifest at {path}"
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def test_ac_prov_013_verification_run_id_is_deterministic(tmp_path):
    inputs = _make_inputs()

    first_root = tmp_path / "first"
    first_root.mkdir()
    first_manifests = _run(first_root, inputs)

    # Then the manifest's verification_run_id is "foo-attempt-2"
    for manifest in first_manifests:
        assert field(manifest, "verification_run_id") == "foo-attempt-2"

    # Given the exact same ProvenanceInputs run a second time
    second_root = tmp_path / "second"
    second_root.mkdir()
    second_manifests = _run(second_root, inputs)

    # Then their verification_run_id fields are identical
    first_ids = [field(m, "verification_run_id") for m in first_manifests]
    second_ids = [field(m, "verification_run_id") for m in second_manifests]
    assert first_ids == second_ids
    assert all(run_id == "foo-attempt-2" for run_id in second_ids)

    # Running again into the same repo_root yields the same id as well.
    third_manifests = _run(first_root, inputs)
    assert [field(m, "verification_run_id") for m in third_manifests] == first_ids