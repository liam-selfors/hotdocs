# hotdocs-criterion: sha256:7cc9934af2217f8b7ca2b2de0a72ee48e1b5882251480d87c1bab6b8f90600f9
import verifier_orchestrator


def test_gate_version_is_readable_without_calling_verify():
    assert hasattr(verifier_orchestrator, "GATE_VERSION")
    value = verifier_orchestrator.GATE_VERSION
    assert isinstance(value, str)
    assert value == "verifier-orchestrator@3.5.0"