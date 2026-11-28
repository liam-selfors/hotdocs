# hotdocs-criterion: sha256:e06af4b56a178235b24c4b59d14fa7734dd366f0fc4f301dbf4e9507a0b20ce0
import verifier_orchestrator


def test_gate_version_is_readable_without_verify():
    # Read GATE_VERSION directly from the imported module, never calling verify.
    assert hasattr(verifier_orchestrator, "GATE_VERSION")
    value = verifier_orchestrator.GATE_VERSION
    assert isinstance(value, str)
    assert value == "verifier-orchestrator@4.0.0"