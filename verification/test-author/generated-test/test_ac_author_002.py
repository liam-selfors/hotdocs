# hotdocs-criterion: sha256:6b1610ffad54aad38cc139118c592273fba4aa64b45257b49e16c5755fb6fe57
import json
import re

import test_author


SENTINEL = "HOTDOCS_GEN_SENTINEL_7f3a9c1e_DO_NOT_LEAK"
SENTINEL_FN = "secret_gen_only_function_b41d"

REPLY_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make():\n"
    "    assert widget_maker.make_widget('a') is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def _write_gen_content(repo_root):
    gen_dir = repo_root / "gen" / "widget-maker"
    gen_dir.mkdir(parents=True)
    src = (
        "# " + SENTINEL + "\n"
        "SENTINEL = " + repr(SENTINEL) + "\n"
        "\n"
        "\n"
        "def " + SENTINEL_FN + "():\n"
        "    return SENTINEL\n"
        "\n"
        "\n"
        "def make_widget(name):\n"
        "    return {'name': name, 'marker': SENTINEL}\n"
    )
    (gen_dir / "widget_maker.py").write_text(src, encoding="utf-8")
    nested = gen_dir / "helpers"
    nested.mkdir()
    (nested / "util.py").write_text(
        "# " + SENTINEL + "\nVALUE = " + repr(SENTINEL) + "\n", encoding="utf-8"
    )
    (gen_dir / ".provenance.json").write_text(
        json.dumps({"note": SENTINEL}), encoding="utf-8"
    )
    return src


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    lines = [
        "import dataclasses",
        "import json",
        "",
        "LOG = " + repr(str(log_path)),
        "",
        "",
        "def _as_dict(b):",
        "    if isinstance(b, dict):",
        "        return dict(b)",
        "    if dataclasses.is_dataclass(b):",
        "        return dict((f.name, getattr(b, f.name)) for f in dataclasses.fields(b))",
        "    try:",
        "        return dict((k, b[k]) for k in b.keys())",
        "    except Exception:",
        "        return dict(vars(b))",
        "",
        "",
        "class ProbeReport:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "        self.tests_run = 1",
        "        self.tests_reached = 1",
        "",
        "    def to_dict(self):",
        "        return dict(ok=self.ok, findings=list(self.findings),",
        "                    tests_run=self.tests_run, tests_reached=self.tests_reached)",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,",
        "          interpreter=None, assets=None):",
        "    record = dict(bundle=_as_dict(criterion_bundle), test_source=test_source)",
        "    with open(LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps(record, default=str) + '\\n')",
        "    return ProbeReport()",
        "",
    ]
    (probe_dir / "test_probe.py").write_text("\n".join(lines), encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given a name\nWhen make_widget is called\n"
            "Then it returns a widget"
        ),
        "requirement_text": "R-WIDGET-MAKER-001 make_widget MUST return a widget.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_criterion_bundle_has_no_field_from_gen_content(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    gen_src = _write_gen_content(repo_root)
    probe_log = tmp_path / "probe_calls.log"
    prompt_log = tmp_path / "prompts.log"
    _write_probe_stand_in(repo_root, probe_log)

    def backend(prompt, model, **params):
        with open(str(prompt_log), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(prompt) + "\n")
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

    bundle = _bundle()
    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "model_call_error") is None

    # The bundle handed on (to test-probe) holds nothing derived from gen/.
    assert probe_log.is_file()
    records = [
        json.loads(line)
        for line in probe_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records
    for record in records:
        seen = record["bundle"]
        assert seen.get("hint_code") in (None, {}, "")
        serialized = json.dumps(seen, default=str)
        assert SENTINEL not in serialized
        assert SENTINEL_FN not in serialized
        for key, value in seen.items():
            assert SENTINEL not in str(value), key
        assert seen.get("component_id") == "comp-widget-maker"
        assert seen.get("criterion_id") == "AC-WIDGET-MAKER-001"

    # No prompt the model saw carries gen/ content.
    prompts = [
        json.loads(line)
        for line in prompt_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert prompts
    for prompt in prompts:
        assert SENTINEL not in prompt
        assert SENTINEL_FN not in prompt

    # The produced file carries no gen/ content either.
    file_value = field(result, "file")
    assert file_value is not None
    content = file_value["content"]
    assert SENTINEL not in content
    assert body(content) == REPLY_FILE

    # The gen/ content itself was left as it was.
    assert (repo_root / "gen" / "widget-maker" / "widget_maker.py").read_text(
        encoding="utf-8"
    ) == gen_src