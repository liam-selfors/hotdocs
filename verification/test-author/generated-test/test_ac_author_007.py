# hotdocs-criterion: sha256:db8470f4fe503af35ed40343bec2b1e25e7d10eece2b7a80a5cd7453d92b16b7
import os
from pathlib import Path

import pytest

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen make is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 - make MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('called\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source)


def _raising_backend(prompt, model, **params):
    raise ConnectionError("network unreachable")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return root


def test_network_error_reported_as_model_call_error(repo_root, tmp_path):
    log_path = tmp_path / "probe_calls.log"
    _plant_probe_stand_in(repo_root, log_path)

    result = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=_raising_backend
    )

    error = field(result, "model_call_error")
    assert error is not None
    assert field(result, "file") is None
    assert field(result, "cache_hit") is False

    # Nothing written for a model-call error.
    verification = repo_root / "verification"
    if verification.exists():
        assert [p for p in verification.rglob("*") if p.is_file()] == []