# hotdocs-criterion: sha256:e49fc65d6693937ce7132869393143137422820c11fdb881b09267b90a0d296d
import json
import re
import types

import pytest

import test_author


EXPECTED_TEST = "def test_generated_placeholder():\n    assert 1 + 1 == 2\n"

BASE_FIELDS = {
    "component_id": "comp-widget-maker",
    "criterion_id": "AC-WIDGET-MAKER-001",
    "covers": "R-WIDGET-MAKER-001",
    "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
    "requirement_text": "R-WIDGET-MAKER-001 - the widget maker MUST make widgets.",
    "interface": "make_widget(name: str) -> dict",
    "glossary": "",
}

EXPECTED_PATH = "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "GATE_VERSION = " + repr("test-probe@1.5.0") + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": list(self.findings),\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
        "        fh.write(json.dumps({" + repr("test_source") + ": test_source}) + " + repr("\n") + ")\n"
        "    return ProbeReport()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + EXPECTED_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run_and_check(repo_root, monkeypatch, bundle):
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(repo_root)
    log_path = repo_root.parent / (repo_root.name + "-probe-calls.log")
    plant_probe_stand_in(repo_root, log_path)
    calls = []

    try:
        result = test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=make_backend(calls)
        )
    except (AttributeError, KeyError) as exc:
        pytest.fail("author_test raised on a bundle without dependency_interfaces: " + repr(exc))

    assert len(calls) >= 1
    assert field(result, "model_call_error") is None

    file_info = field(result, "file")
    assert file_info is not None
    assert file_info["path"] == EXPECTED_PATH
    assert body(file_info["content"]) == EXPECTED_TEST

    written = repo_root / EXPECTED_PATH
    assert written.is_file()
    assert body(written.read_text(encoding="utf-8")) == EXPECTED_TEST

    assert log_path.is_file()
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    assert json.loads(lines[-1])["test_source"] == EXPECTED_TEST


def test_object_bundle_without_dependency_interfaces_attribute(tmp_path, monkeypatch):
    bundle = types.SimpleNamespace(**BASE_FIELDS)
    assert not isinstance(bundle, dict)
    assert not hasattr(bundle, "dependency_interfaces")

    run_and_check(tmp_path / "repo-object", monkeypatch, bundle)


def test_dict_bundle_without_dependency_interfaces_key(tmp_path, monkeypatch):
    bundle = dict(BASE_FIELDS)
    assert "dependency_interfaces" not in bundle

    run_and_check(tmp_path / "repo-dict", monkeypatch, bundle)