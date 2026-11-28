# hotdocs-criterion: sha256:1da4fcc491815323cac3953c8db49bf4535eb2ebc9ad4411c202cf000f4980ad
import json
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TEST_FILE = (
    "def test_placeholder():\n"
    "    assert 1 + 1 == 2\n"
)


def mock_backend(prompt, model, **params):
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    text = (
        "-----BEGIN FILE " + nonce + "-----\n"
        + TEST_FILE
        + "\n-----END FILE " + nonce + "-----"
    )
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.5.0'\n"
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(kwargs, default=repr) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle(testing):
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": testing,
    }


def run_scenario(tmp_path, monkeypatch, name, testing):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-probe-calls.log")
    plant_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    result = test_author.author_test(
        make_bundle(testing), "mock", repo_root=repo_root, llm_backend=mock_backend
    )
    assert field(result, "model_call_error") is None

    assert log_path.is_file(), "the test-probe stand-in was never called"
    lines = [
        line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return [json.loads(line) for line in lines]


def test_drivers_from_testing_driver_heading(tmp_path, monkeypatch):
    testing = (
        "# Testing widget-maker\n\nSome mechanics."
        "\n## Test driver: browser\n\nUse the browser fixture."
    )
    calls = run_scenario(tmp_path, monkeypatch, "with-driver", testing)
    assert len(calls) == 1
    assert "drivers" in calls[0]
    assert calls[0]["drivers"] == ["browser"]


def test_drivers_empty_when_testing_empty(tmp_path, monkeypatch):
    calls = run_scenario(tmp_path, monkeypatch, "no-driver", "")
    assert len(calls) == 1
    assert "drivers" in calls[0]
    assert calls[0]["drivers"] == []