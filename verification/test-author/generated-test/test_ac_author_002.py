# hotdocs-criterion: sha256:e2d4259242ad96d27388b2d76bcd935520efb0363c6b99aa691b16c310f564aa
import json
import re
import uuid
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

REPLY_FILE = (
    "import test_author_target_placeholder\n"
    "\n"
    "\n"
    "def test_placeholder():\n"
    "    assert test_author_target_placeholder.run() is not None\n"
)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import dataclasses\n"
        "import json\n"
        "from collections.abc import Mapping\n"
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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def _items(bundle):\n"
        "    if isinstance(bundle, Mapping):\n"
        "        return {str(k): bundle[k] for k in bundle.keys()}\n"
        "    if dataclasses.is_dataclass(bundle):\n"
        "        return {f.name: getattr(bundle, f.name) for f in dataclasses.fields(bundle)}\n"
        "    try:\n"
        "        return {str(k): bundle[k] for k in bundle.keys()}\n"
        "    except Exception:\n"
        "        return dict(getattr(bundle, '__dict__', {}))\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None, **kwargs):\n"
        "    items = _items(criterion_bundle)\n"
        "    record = {\n"
        "        'keys': sorted(items.keys()),\n"
        "        'items': repr(items),\n"
        "        'bundle_repr': repr(criterion_bundle),\n"
        "        'module_name': repr(module_name),\n"
        "    }\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _plant_target_gen_content(repo_root, sentinel):
    gen_dir = repo_root / "gen" / "widget-maker"
    (gen_dir / "sub").mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text(
        "# implementation marker " + sentinel + "\n"
        "SECRET_IMPL = " + repr(sentinel + "_CONST") + "\n"
        "\n"
        "\n"
        "def make_widget(name):\n"
        "    return " + repr(sentinel + "_RETURN") + " + name\n",
        encoding="utf-8",
    )
    (gen_dir / "sub" / "extra.py").write_text(
        "HELPER = " + repr(sentinel + "_HELPER") + "\n", encoding="utf-8"
    )
    (gen_dir / ".provenance.json").write_text(
        json.dumps({"note": sentinel + "_PROVENANCE"}), encoding="utf-8"
    )


def test_criterion_bundle_carries_no_gen_content(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    sentinel = "HOTDOCS_GEN_SENTINEL_" + uuid.uuid4().hex
    interface_marker = "INTERFACE_MARKER_" + uuid.uuid4().hex

    _plant_target_gen_content(repo_root, sentinel)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    prompt_log = tmp_path / "prompts.log"

    def mock_backend(prompt, model, **params):
        with open(prompt_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt}) + "\n")
        nonce = re.findall(NONCE_RE, prompt)[-1]
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

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget name\nWhen make_widget is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 — make_widget MUST return a widget.",
        "interface": "# Library\n\nmake_widget(name: str) -> str\n\n" + interface_marker + "\n",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None

    # The bundle as the model saw it: every prompt carries the interface but
    # nothing from gen/widget-maker/.
    assert prompt_log.is_file(), "the mock model was never called"
    prompts = [
        json.loads(line)["prompt"]
        for line in prompt_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert prompts
    for prompt in prompts:
        assert interface_marker in prompt
        assert sentinel not in prompt

    # The bundle as handed on to test-probe: no field derived from gen content.
    assert probe_log.is_file(), "the test-probe stand-in was never called"
    records = [
        json.loads(line)
        for line in probe_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records
    for record in records:
        assert "hint_code" not in record["keys"]
        assert sentinel not in record["items"]
        assert sentinel not in record["bundle_repr"]

    # Nothing the component returned or wrote is derived from gen content.
    file_value = field(result, "file")
    assert file_value is not None
    content = file_value["content"]
    assert sentinel not in content
    assert body(content) == REPLY_FILE

    written = repo_root / file_value["path"]
    assert written.is_file()
    assert sentinel not in written.read_text(encoding="utf-8")

    for name in (
        "component_id",
        "criterion_id",
        "model",
        "seed",
        "prompt_version",
        "cache_hit",
        "model_call_error",
        "repair_attempts",
        "probe_findings",
    ):
        assert sentinel not in repr(field(result, name))

    for sub in ("verification", ".hotdocs"):
        root = repo_root / sub
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                assert sentinel not in text, str(path)