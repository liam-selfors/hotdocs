# hotdocs-criterion: sha256:386ed3aa3aa3a7e9225a20ab4ff5bba97e98cb955160082eb8cdb8ee970ec6ea
import json
import re

import pytest

import test_author


CANONICAL_MODEL = "mock-canonical-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 — A widget MUST be made.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'module_name': module_name}) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _write_generator_provenance(repo_root, model_a):
    # The component's current code, produced by the generator with model A.
    gen_dir = repo_root / "gen" / "widget-maker"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text(
        "def make_widget(name):\n    return {'name': name}\n", encoding="utf-8"
    )
    manifest = {
        "component_id": "comp-widget-maker",
        "model": model_a,
        "generator_model": model_a,
        "seed": 0,
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize(
    "model_a",
    [
        "anthropic:claude-opus-4",
        "ollama:llama3.1:8b",
        "some-other-generator-model",
        CANONICAL_MODEL,
    ],
)
def test_author_test_calls_model_with_canonical_model_only(tmp_path, monkeypatch, model_a):
    repo_root = tmp_path / ("repo_" + re.sub(r"[^a-zA-Z0-9]", "_", model_a))
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / ("probe_log_" + repo_root.name + ".txt")
    _write_probe_stand_in(repo_root, probe_log)
    _write_generator_provenance(repo_root, model_a)

    calls = []
    test_body = "def test_widget():\n    assert True\n"

    def mock_backend(prompt, model, **params):
        calls.append(model)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_body
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _bundle(), CANONICAL_MODEL, 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert len(calls) >= 1
    for called_model in calls:
        assert called_model == CANONICAL_MODEL
    if model_a != CANONICAL_MODEL:
        assert model_a not in calls
    assert field(result, "model") == CANONICAL_MODEL