import verifier_orchestrator


def test_ac_verify_017_gate_version_readable_without_verify(monkeypatch):
    calls = []

    def _forbidden_verify(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("verify must not be called to read GATE_VERSION")

    # Guard: reading GATE_VERSION must never depend on calling verify.
    if hasattr(verifier_orchestrator, "verify"):
        monkeypatch.setattr(verifier_orchestrator, "verify", _forbidden_verify)

    value = verifier_orchestrator.GATE_VERSION

    assert isinstance(value, str)
    assert value == "verifier-orchestrator@2.0.0"
    assert calls == []