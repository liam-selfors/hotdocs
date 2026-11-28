# hotdocs-criterion: sha256:c845c1569676453c75d20ff0477ba534b3e25ca04a16dfcf5d4aa6bc626c31ee
import json
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


MOCK_FILE = "def test_placeholder():\n    assert True\n"


def make_backend():
    def backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + MOCK_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    src = (
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(kwargs, default=repr) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(src, encoding="utf-8")


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


def run_scenario(base, monkeypatch, testing):
    repo_root = base / "repo"
    repo_root.mkdir(parents=True)
    log_path = base / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    result = test_author.author_test(
        make_bundle(testing), "mock", repo_root=repo_root, llm_backend=make_backend()
    )
    assert field(result, "model_call_error") is None
    assert log_path.is_file()
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_drivers_from_test_driver_heading(tmp_path, monkeypatch):
    testing = (
        "# Testing widget-maker\n\nSome mechanics."
        + "\n## Test driver: browser\n\nUse the browser fixture."
    )
    calls = run_scenario(tmp_path / "with_driver", monkeypatch, testing)
    assert len(calls) == 1
    assert calls[0].get("drivers") == ["browser"]


def test_drivers_empty_when_testing_empty(tmp_path, monkeypatch):
    calls = run_scenario(tmp_path / "no_driver", monkeypatch, "")
    assert len(calls) == 1
    assert "drivers" in calls[0]
    assert calls[0]["drivers"] == []