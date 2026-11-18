# hotdocs-criterion: sha256:b8e7f1ad41a1c33c136ded41f6b22138b7dd0b9aec46970d119cd170599643c5
import verifier_orchestrator


def test_gate_version_is_readable_without_calling_verify():
    # Given the verifier-orchestrator module is imported
    # When GATE_VERSION is read, without calling verify
    value = verifier_orchestrator.GATE_VERSION

    # Then it equals "verifier-orchestrator@2.2.0"
    assert isinstance(value, str)
    assert value == "verifier-orchestrator@2.2.0"