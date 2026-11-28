# hotdocs-criterion: sha256:63d5a8d847348ea9a9495005d527d2d0ef01151e0e11bffd8ffc0b619d23c49a
import json
import re
from pathlib import Path

import test_author


GOOD = "def test_placeholder():\n    assert True"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = Path(repo_root) / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
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
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": list(self.findings),\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
        "        fh.write(json.dumps({" + repr("test_source") + ": test_source}) + " + repr("\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + GOOD
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def assert_completed(result, repo_root, calls, log_path):
    assert len(calls) >= 1
    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    path = field(file_entry, "path")
    content = field(file_entry, "content")
    assert body(content) == GOOD
    written = Path(repo_root) / path
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 1
    assert json.loads(lines[-1])["test_source"] == GOOD


class PlainBundle:
    def __init__(self):
        self.component_id = "comp-widget-maker"
        self.criterion_id = "AC-WIDGET-MAKER-001"
        self.covers = "R-WIDGET-MAKER-001"
        self.criterion_text = "Given a widget\nWhen it is made\nThen it exists"
        self.requirement_text = "R-WIDGET-MAKER-001 - widgets MUST be made."
        self.interface = "make_widget(name: str) -> dict"
        self.glossary = ""
        self.testing = ""


def test_object_bundle_without_dependency_interfaces_completes(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_obj"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls_obj.log"
    plant_probe_stand_in(repo_root, log_path)

    bundle = PlainBundle()
    assert not hasattr(bundle, "dependency_interfaces")
    assert not isinstance(bundle, dict)

    calls = []
    try:
        result = test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=make_backend(calls)
        )
    except AttributeError as exc:
        raise AssertionError("author_test raised AttributeError: " + repr(exc))

    assert_completed(result, repo_root, calls, log_path)


def test_dict_bundle_without_dependency_interfaces_completes(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_dict"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls_dict.log"
    plant_probe_stand_in(repo_root, log_path)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - widgets MUST be made.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "testing": "",
    }
    assert "dependency_interfaces" not in bundle

    calls = []
    try:
        result = test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=make_backend(calls)
        )
    except KeyError as exc:
        raise AssertionError("author_test raised KeyError: " + repr(exc))

    assert_completed(result, repo_root, calls, log_path)