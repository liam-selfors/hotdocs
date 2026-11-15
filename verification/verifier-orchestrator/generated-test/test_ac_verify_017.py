import verifier_orchestrator


def test_gate_version_readable_without_calling_verify():
    # Read GATE_VERSION directly from the imported module; verify is never called.
    assert hasattr(verifier_orchestrator, "GATE_VERSION")
    value = verifier_orchestrator.GATE_VERSION
    assert isinstance(value, str)
    assert value == "verifier-orchestrator@2.0.0"