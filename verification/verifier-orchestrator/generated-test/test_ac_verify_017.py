# hotdocs-criterion: sha256:7d9900fbe147d1c4da731e6ea0faad2c7fcebc8d32ecf6e3159964d6814e0fa8
import verifier_orchestrator


def test_gate_version_is_readable_without_calling_verify():
    value = verifier_orchestrator.GATE_VERSION
    assert isinstance(value, str)
    assert value == "verifier-orchestrator@3.5.0"