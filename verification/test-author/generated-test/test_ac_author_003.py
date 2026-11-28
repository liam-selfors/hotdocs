# hotdocs-criterion: sha256:15ff7e1a7ddbc9ac9b191d5ac225d9e6f71a956a10b9555b7d7f9449c78d396a
import json
import re

import pytest

import test_author


CANONICAL_MODEL = "canonical-mock-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


TEST_BODY = "def test_placeholder():\n    assert True\n"


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given a widget spec\n"
            "When make_widget runs\n"
            "Then it returns a widget"
        ),
        "requirement_text": "**R-WIDGET-MAKER-001** - make_widget MUST return a widget.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe_stand_in(repo_root, log_path):
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


def plant_generator_provenance(repo_root, model_a):
    # The component's current code, as the generator produced it with model A.
    gen_dir = repo_root / "gen" / "widget-maker"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text(
        "def make_widget(name):\n    return {'name': name}\n", encoding="utf-8"
    )
    manifest = {
        "component_id": "comp-widget-maker",
        "model": model_a,
        "generator": {"model": model_a},
        "files": ["widget_maker.py"],
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


def make_backend(model_log):
    def backend(prompt, model, **params):
        with open(model_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
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

    return backend


@pytest.mark.parametrize(
    "model_a",
    [
        "anthropic:claude-opus-5-5",
        "ollama:llama3.1:8b",
        "some-other-generator-model",
    ],
)
def test_author_test_calls_model_with_canonical_model_regardless_of_generator_model(
    tmp_path, monkeypatch, model_a
):
    repo_root = tmp_path / ("repo-" + re.sub(r"[^a-z0-9]+", "-", model_a.lower()))
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / ("probe-" + repo_root.name + ".log")
    model_log = tmp_path / ("models-" + repo_root.name + ".log")

    plant_probe_stand_in(repo_root, probe_log)
    plant_generator_provenance(repo_root, model_a)

    bundle = make_bundle()
    result = test_author.author_test(
        bundle,
        CANONICAL_MODEL,
        0,
        repo_root=repo_root,
        llm_backend=make_backend(model_log),
    )

    assert field(result, "model_call_error") is None

    assert model_log.is_file(), "the model was never called"
    calls = [
        json.loads(line)
        for line in model_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(calls) >= 1
    for call in calls:
        assert call["model"] == CANONICAL_MODEL
        assert call["model"] != model_a
        assert model_a not in call["model"]

    assert field(result, "model") == CANONICAL_MODEL

    file = field(result, "file")
    assert file is not None
    assert body(field(file, "content")) == TEST_BODY