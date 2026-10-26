"""One test per AC-ASSEMBLE-* criterion in
specs/components/spec-bundle-assembler/acceptance/.
"""

from pathlib import Path

import pytest

from spec_bundle_assembler import PreconditionFailureError, assemble, assemble_criterion


def test_ac_assemble_001_no_acceptance_content(corpus_root):
    bundle = assemble("comp-foo", corpus_root)
    assert "do_the_thing is called" not in bundle.spec
    assert "do_the_thing is called" not in bundle.interface
    assert "do_the_thing is called" not in bundle.constraints
    assert "AC-FOO-001" not in bundle.spec


def test_ac_assemble_002_dependency_interface_only(corpus_root):
    bundle = assemble("comp-foo", corpus_root)
    dep = bundle.dependency_interfaces["comp-bar"]
    assert "bar_get" in dep
    assert "Bar MUST cache" not in dep  # requirements/ excluded
    assert "Determinism" not in dep  # constraints.md excluded


def test_ac_assemble_003_vars_content(corpus_root):
    bundle = assemble("comp-foo", corpus_root)
    assert "Where foo lives" in bundle.vars["VAR-FOO-URL"]


def test_ac_assemble_004_glossary_matches_exactly(corpus_root):
    bundle = assemble("comp-foo", corpus_root)
    assert bundle.glossary == (corpus_root / "specs" / "glossary.md").read_text()


def test_ac_assemble_005_precondition_failure_on_dirty_corpus(corpus_root):
    # Break the corpus at hard-fail severity: an undeclared depends_on target.
    comp_md = corpus_root / "specs" / "components" / "foo" / "component.md"
    comp_md.write_text(comp_md.read_text().replace("depends_on: [comp-bar]", "depends_on: [comp-nonexistent]"))
    with pytest.raises(PreconditionFailureError):
        assemble("comp-foo", corpus_root)


def test_ac_assemble_006_deterministic(corpus_root):
    b1 = assemble("comp-foo", corpus_root)
    b2 = assemble("comp-foo", corpus_root)
    assert b1.to_dict() == b2.to_dict()


def test_ac_assemble_007_hash_reproducible(corpus_root):
    bundle = assemble("comp-foo", corpus_root)
    assert bundle.spec_bundle_hash.startswith("sha256:")
    from spec_bundle_assembler import _compute_hash
    recomputed = _compute_hash({
        k: v for k, v in bundle.to_dict().items()
        if k not in ("hint_code", "spec_bundle_hash")
    })
    assert recomputed == bundle.spec_bundle_hash


def test_ac_assemble_008_hint_mode_is_additive(corpus_root):
    gen_dir = corpus_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text("def do_the_thing():\n    pass\n")

    cold = assemble("comp-foo", corpus_root, mode="cold")
    hint = assemble("comp-foo", corpus_root, mode="hint")

    assert hint.hint_code == {"foo.py": "def do_the_thing():\n    pass\n"}
    cold_dict = cold.to_dict()
    hint_dict = hint.to_dict()
    del cold_dict["hint_code"]
    del hint_dict["hint_code"]
    assert cold_dict == hint_dict


def test_ac_assemble_009_criterion_bundle_is_narrow(corpus_root):
    gen_dir = corpus_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text("SECRET_IMPLEMENTATION = True\n")

    bundle = assemble_criterion("comp-foo", "AC-FOO-001", corpus_root)
    assert bundle.covers == "R-FOO-001"
    assert "do_the_thing is called" in bundle.criterion_text
    assert "Foo MUST do the one thing" in bundle.requirement_text
    assert "SECRET_IMPLEMENTATION" not in bundle.interface
    assert "SECRET_IMPLEMENTATION" not in bundle.criterion_text
    assert "Determinism" not in bundle.interface  # constraints.md excluded


def test_ac_assemble_010_dependency_context_is_purpose_only(corpus_root):
    bundle = assemble("comp-foo", corpus_root)
    # component_context's own regexp_extract keeps one trailing newline
    # from the Purpose section's source text (already verified in
    # graph-query-engine's own test suite) -- .strip() isolates the
    # content assertion this criterion actually cares about.
    assert bundle.dependency_context["comp-bar"].strip() == "Caches results."
    assert "D13" not in bundle.dependency_context["comp-bar"]
