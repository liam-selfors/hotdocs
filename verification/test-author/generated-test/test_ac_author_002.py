# hotdocs-criterion: sha256:82e99d197013932f485e1f0f1c9f84f17471acb15186a309febafbb5f9028d94
"""AC-AUTHOR-002: a CriterionBundle for a component with existing
gen/<component>/ content contains no field derived from that content.

The test plants real-looking gen/<component>/ source carrying a unique
marker under a fresh repo_root, then calls author_test with a mock model
and a test-probe stand-in. The bundle as test-author hands it on (to the
model's prompt and to test-probe) is inspected. Neither may hold anything
derived from the planted gen/<component>/ content.
"""

import json
import re
import uuid

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def _write_probe_stand_in(repo_root, log_path):
    target = repo_root / "gen" / "test-probe" / "test_probe.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "import dataclasses\n"
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
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
        "def _as_dict(bundle):\n"
        "    if isinstance(bundle, dict):\n"
        "        return dict(bundle)\n"
        "    if dataclasses.is_dataclass(bundle):\n"
        "        return dataclasses.asdict(bundle)\n"
        "    try:\n"
        "        return {k: bundle[k] for k in bundle.keys()}\n"
        "    except Exception:\n"
        "        return dict(vars(bundle))\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    record = {\n"
        "        'bundle': _as_dict(criterion_bundle),\n"
        "        'test_source': test_source,\n"
        "        'module_name': module_name,\n"
        "    }\n"
        "    with open(LOG, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(record, default=str) + '\\n')\n"
        "    return _Report()\n"
    )
    target.write_text(source, encoding="utf-8")


def _plant_gen_content(repo_root, marker):
    gen_dir = repo_root / "gen" / "widget-maker"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text(
        "# " + marker + " implementation header\n"
        "SECRET_CONSTANT = " + repr(marker) + "\n"
        "\n"
        "\n"
        "def make_widget_" + marker.lower() + "(name):\n"
        "    return {'name': name, 'tag': " + repr(marker) + "}\n",
        encoding="utf-8",
    )
    nested = gen_dir / "internals"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / ("helper_" + marker.lower() + ".py")).write_text(
        "VALUE = " + repr(marker) + "\n", encoding="utf-8"
    )
    (gen_dir / ".provenance.json").write_text(
        json.dumps({"note": marker}), encoding="utf-8"
    )


def _read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_bundle_carries_nothing_from_existing_gen_content(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    probe_log = logs / "probe_calls.jsonl"
    prompt_log = logs / "prompts.jsonl"

    marker = "HOTDOCSGENSECRET" + uuid.uuid4().hex.upper()
    _plant_gen_content(repo_root, marker)
    _write_probe_stand_in(repo_root, probe_log)

    monkeypatch.chdir(repo_root)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given a name\nWhen make_widget is called\n"
            "Then it returns a widget with that name"
        ),
        "requirement_text": (
            "**R-WIDGET-MAKER-001** - make_widget MUST return a widget "
            "named as given."
        ),
        "interface": "# Library\n\n```\nmake_widget(name: str) -> dict\n```\n",
        "glossary": "",
        "dependency_interfaces": {},
    }
    bundle_before = json.dumps(bundle, sort_keys=True)

    test_file = (
        "import widget_maker\n"
        "\n"
        "\n"
        "def test_make_widget():\n"
        "    assert widget_maker.make_widget('a')['name'] == 'a'\n"
    )

    def mock_backend(prompt, model, **params):
        with open(prompt_log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(prompt) + "\n")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_file
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    # The authoring actually ran end to end, so the inspection below is real.
    assert field(result, "model_call_error") is None
    prompts = _read_jsonl(prompt_log)
    assert prompts, "the mock model was never called"
    probe_calls = _read_jsonl(probe_log)
    assert probe_calls, "the test-probe stand-in was never called"

    # The bundle test-author hands on contains nothing from gen/<component>/.
    for call in probe_calls:
        handed_bundle = call["bundle"]
        assert marker not in json.dumps(handed_bundle, default=str)
        assert marker.lower() not in json.dumps(handed_bundle, default=str)
        assert "hint_code" not in handed_bundle
        assert handed_bundle.get("component_id") == "comp-widget-maker"

    # Nothing derived from gen/<component>/ reaches the model either.
    for prompt in prompts:
        assert marker not in prompt
        assert marker.lower() not in prompt
        assert "SECRET_CONSTANT" not in prompt

    # The caller's bundle was not enriched with gen/<component>/ content.
    assert json.dumps(bundle, sort_keys=True) == bundle_before

    # The result itself carries nothing from gen/<component>/.
    file_value = field(result, "file")
    assert file_value is not None
    assert marker not in file_value["content"]
    assert body(file_value["content"]) == test_file