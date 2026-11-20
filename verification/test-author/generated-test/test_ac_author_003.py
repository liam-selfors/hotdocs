# hotdocs-criterion: sha256:40d9e31f06eb8399edca2500cd9cc2301f91e91a588ff45c754b206e5598ccc1
import json
import re

import pytest

import test_author


CANONICAL_MODEL = "canonical-model-x1"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
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
        "        return {\"ok\": self.ok, \"findings\": list(self.findings),\n"
        "                \"tests_run\": self.tests_run, \"tests_reached\": self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG_PATH, \"a\") as fh:\n"
        "        fh.write(\"probe\\n\")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source)


def _write_generator_provenance(repo_root, model_a):
    gen_dir = repo_root / "gen" / "widget-maker"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text("def make_widget():\n    return 1\n")
    manifest = {
        "component_id": "comp-widget-maker",
        "model": model_a,
        "generation_result": {
            "component_id": "comp-widget-maker",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": model_a,
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"widget_maker.py": "def make_widget():\n    return 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize("model_a", ["model-a-alpha", "ollama:llama3.1:8b"])
def test_author_test_uses_canonical_model_regardless_of_generator_model(
    tmp_path, monkeypatch, model_a
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)
    _write_generator_provenance(repo_root, model_a)

    seen_models = []

    def mock_backend(prompt, model, **params):
        seen_models.append(model)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        body = "def test_placeholder():\n    assert True"
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body + "\n"
            + "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen make_widget runs\nThen it returns 1",
        "requirement_text": "R-WIDGET-MAKER-001 make_widget MUST return 1.",
        "interface": "make_widget() -> int",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, CANONICAL_MODEL, 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert seen_models, "the model backend was never called"
    for m in seen_models:
        assert m == CANONICAL_MODEL
        assert m != model_a
    assert field(result, "model") == CANONICAL_MODEL
    assert field(result, "model") != model_a