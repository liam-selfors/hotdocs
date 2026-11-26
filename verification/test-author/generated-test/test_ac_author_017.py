# hotdocs-criterion: sha256:f492a6d26bbb228c30ffaf14789de11f8708c5d82686d7ae4a4decb01f2a2159
import json
import re

import pytest

import test_author


MOCK_TEST = "def test_placeholder():\n    assert 1 + 1 == 2\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def make_backend(calls_log):
    def backend(prompt, model, **params):
        with open(calls_log, "a", encoding="utf-8") as f:
            f.write("call\n")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + MOCK_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def plant_probe(repo_root, probe_log):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "import json",
        "",
        "",
        "class _Report:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "        self.tests_run = 1",
        "        self.tests_reached = 1",
        "",
        "    def to_dict(self):",
        "        return {'ok': self.ok, 'findings': list(self.findings),",
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,",
        "          interpreter=None, assets=None, drivers=None):",
        "    with open(" + repr(str(probe_log)) + ", 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({'module_name': module_name}) + '\\n')",
        "    return _Report()",
        "",
    ]
    (probe_dir / "test_probe.py").write_text("\n".join(lines), encoding="utf-8")


BASE_FIELDS = {
    "component_id": "comp-widget-maker",
    "criterion_id": "AC-WIDGET-MAKER-001",
    "covers": "R-WIDGET-MAKER-001",
    "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
    "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be made.",
    "interface": "make_widget(name: str) -> dict",
    "glossary": "",
}

EXPECTED_PATH = "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"


class PlainBundle:
    def __init__(self, values):
        for k, v in values.items():
            setattr(self, k, v)


def run_and_check(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    probe_log = tmp_path / "probe_calls.log"
    calls_log = tmp_path / "model_calls.log"
    plant_probe(repo_root, probe_log)

    try:
        result = test_author.author_test(
            bundle, "mock", 0,
            repo_root=repo_root, llm_backend=make_backend(calls_log),
        )
    except (AttributeError, KeyError) as exc:
        pytest.fail("author_test raised " + type(exc).__name__ + ": " + repr(exc))

    assert field(result, "model_call_error") is None
    assert calls_log.is_file() and calls_log.read_text(encoding="utf-8").count("call") >= 1
    assert probe_log.is_file() and probe_log.read_text(encoding="utf-8").strip() != ""

    file = field(result, "file")
    assert file is not None
    assert field(file, "path") == EXPECTED_PATH
    assert body(field(file, "content")) == MOCK_TEST

    written = repo_root / EXPECTED_PATH
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == field(file, "content")
    return result


def test_object_bundle_without_dependency_interfaces_attribute(tmp_path, monkeypatch):
    bundle = PlainBundle(BASE_FIELDS)
    assert not isinstance(bundle, dict)
    assert not hasattr(bundle, "dependency_interfaces")
    run_and_check(tmp_path, monkeypatch, bundle)


def test_dict_bundle_without_dependency_interfaces_key(tmp_path, monkeypatch):
    bundle = dict(BASE_FIELDS)
    assert "dependency_interfaces" not in bundle
    run_and_check(tmp_path, monkeypatch, bundle)