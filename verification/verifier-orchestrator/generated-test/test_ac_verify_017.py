# hotdocs-criterion: sha256:b2af422f0a5dd0077a955661c88c3beffc6658d7143fa3836973c67279be86e4
import verifier_orchestrator


def test_gate_version_readable_without_calling_verify():
    value = verifier_orchestrator.GATE_VERSION
    assert isinstance(value, str)
    assert value == "verifier-orchestrator@2.3.0"