# hotdocs-criterion: sha256:68200aa4338d6c113c3d417fffca01399d220377619e93005a869412d1af81be
import json
import re

import pytest

import test_author


CANONICAL_MODEL = "canonical-model-z"

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

TEST_BODY = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def write_probe_stand_in(repo_root, log_path):
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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def write_generator_provenance(repo_root, generator_model):
    # The component's current code was produced by the generator using model A.
    gen_dir = repo_root / "gen" / "widget-maker"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text(
        "def make_widget():\n    return {}\n", encoding="utf-8"
    )
    manifest = {
        "component_id": "comp-widget-maker",
        "model": generator_model,
        "generator_model": generator_model,
        "seed": 0,
    }
    (gen_dir / ".provenance.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "generator_model",
    ["anthropic:claude-generator-a", "ollama:llama3.1:8b"],
)
def test_author_test_calls_canonical_model_regardless_of_generator_model(
    tmp_path, monkeypatch, generator_model
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)
    write_generator_provenance(repo_root, generator_model)

    backend_log = tmp_path / "backend_calls.log"

    def mock_backend(prompt, model, **params):
        with open(backend_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = NONCE_RE.findall(prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_BODY
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        make_bundle(),
        CANONICAL_MODEL,
        0,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert field(result, "model_call_error") is None

    assert backend_log.is_file(), "the model backend was never called"
    calls = [
        json.loads(line)
        for line in backend_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(calls) >= 1

    # Then: every model call uses the canonical model, never model A.
    for call in calls:
        assert call["model"] == CANONICAL_MODEL
        assert call["model"] != generator_model

    # The result records the canonical model as the one used.
    assert field(result, "model") == CANONICAL_MODEL