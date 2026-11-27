# hotdocs-criterion: sha256:2c362a170ee68caf17e2dae88698e2a7f47af7e1a54010d677777b549e430232
import socket

import pytest

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as f:\n"
        "        f.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    "exc_factory",
    [
        lambda: ConnectionError("connection refused"),
        lambda: socket.gaierror("name or service not known"),
    ],
)
def test_network_error_from_model_is_reported_as_model_call_error(
    tmp_path, monkeypatch, exc_factory
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    probe_log = tmp_path / "probe_calls.log"
    _plant_probe_stand_in(repo_root, probe_log)

    calls_log = tmp_path / "model_calls.log"

    def mock_backend(prompt, model, **params):
        with open(calls_log, "a", encoding="utf-8") as f:
            f.write("call\n")
        raise exc_factory()

    result = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert calls_log.is_file(), "the mock model was never called"

    assert field(result, "model_call_error") is not None
    assert field(result, "file") is None
    assert field(result, "cache_hit") is False