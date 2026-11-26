# hotdocs-criterion: sha256:3390df9a972a4fbfeb00dc9fd4b5fa7ed435ca41aec00e783f5d87b7ceb98581
import re
from pathlib import Path

import pytest

import test_author


SENTINEL = "HOTDOCS_GEN_ONLY_SENTINEL_4b7e91d2c3a8"

GEN_SOURCE = (
    "# " + SENTINEL + " implementation detail comment\n"
    "def make_widget_" + SENTINEL.lower() + "(size):\n"
    "    return {'size': size, 'marker': " + repr(SENTINEL) + "}\n"
)

REPLY_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make():\n"
    "    assert widget_maker.make(1) is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a size\nWhen make is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 - make(size) MUST return a widget.",
        "interface": "# Library\n\n```\nmake(size: int) -> dict\n```\n",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _plant_gen_content(repo_root, layout):
    base = repo_root / "gen" / "widget-maker"
    base.mkdir(parents=True)
    if layout == "flat":
        (base / "widget_maker.py").write_text(GEN_SOURCE, encoding="utf-8")
    else:
        pkg = base / "widget_maker"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(GEN_SOURCE, encoding="utf-8")
    (base / "helpers.py").write_text(
        "HELPER = " + repr(SENTINEL + "_helper") + "\n", encoding="utf-8"
    )
    (base / ".provenance.json").write_text(
        '{"note": ' + repr(SENTINEL + "_provenance").replace("'", '"') + "}\n",
        encoding="utf-8",
    )


def _plant_probe(repo_root, log):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    src = (
        "GATE_VERSION = 'test-probe@1.5.0'\n"
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
        "        return {'ok': True, 'findings': [], 'tests_run': 1, 'tests_reached': 1}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None):\n"
        "    with open(" + repr(str(log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(test_source) + ' ' + repr(criterion_bundle) + ' '\n"
        "                 + repr(module_name) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(src, encoding="utf-8")


@pytest.mark.parametrize("layout", ["flat", "package"])
def test_bundle_and_prompt_carry_no_gen_content(tmp_path, monkeypatch, layout):
    repo_root = tmp_path / ("repo_" + layout)
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    _plant_gen_content(repo_root, layout)
    probe_log = tmp_path / ("probe_calls_" + layout + ".log")
    _plant_probe(repo_root, probe_log)

    bundle = _bundle()

    # Inspect the bundle itself: no field holds anything from gen/widget-maker/.
    for key, value in bundle.items():
        assert SENTINEL not in repr(value), key
        assert GEN_SOURCE not in repr(value), key

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"

    # Nothing derived from gen/widget-maker/ reached the model.
    for prompt in prompts:
        assert SENTINEL not in prompt
        assert SENTINEL.lower() not in prompt
        assert GEN_SOURCE not in prompt
        assert GEN_SOURCE.splitlines()[1] not in prompt

    # Nothing derived from gen/widget-maker/ reached the probe's bundle.
    assert probe_log.is_file(), "the test-probe stand-in was never called"
    log_text = probe_log.read_text(encoding="utf-8")
    assert SENTINEL not in log_text
    assert SENTINEL.lower() not in log_text

    # The returned and written file is the model's reply, nothing from gen/.
    file_ = field(result, "file")
    assert file_ is not None
    content = file_["content"]
    assert SENTINEL not in content
    assert body(content) == REPLY_FILE

    written = repo_root / file_["path"]
    assert written.is_file()
    written_text = written.read_text(encoding="utf-8")
    assert written_text == content
    assert SENTINEL not in written_text

    # The gen/ content is still there, untouched: it was simply never used.
    if layout == "flat":
        gen_file = repo_root / "gen" / "widget-maker" / "widget_maker.py"
    else:
        gen_file = repo_root / "gen" / "widget-maker" / "widget_maker" / "__init__.py"
    assert gen_file.read_text(encoding="utf-8") == GEN_SOURCE