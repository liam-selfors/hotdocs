# hotdocs-criterion: sha256:487bf8056dfdb4e2f9ddffdc9808f6c25d1eb02dab4e6a26030cd00dbc75c13d
import verifier_orchestrator


def test_gate_version_is_readable_without_calling_verify():
    value = verifier_orchestrator.GATE_VERSION
    assert isinstance(value, str)
    assert value == "verifier-orchestrator@3.5.0"