# hotdocs-criterion: sha256:751dc74d3ff4c162ff8f38cdfaba9cedd33bee06b8c60d1c98365d53f7df9beb
import re
from pathlib import Path

import test_author


EXPECTED_LINE = (
    "- A unit file (`constraints.md`, or anything under `requirements/`, "
    "`interface/` or `acceptance/`) carries no frontmatter at all."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = Path(repo_root) / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "GATE_VERSION = " + repr("test-probe@1.4.0") + "\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings, tests_run, tests_reached):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = tests_run\n"
        "        self.tests_reached = tests_reached\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": [dict(f) for f in self.findings],\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
        "        fh.write(" + repr("probe") + " + " + repr("\n") + ")\n"
        "    return ProbeReport(True, [], 1, 1)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_first_prompt_contains_unit_file_frontmatter_rule(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        body = "def test_placeholder():\n    assert True\n"
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body
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
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert field(result, "criterion_id") == "AC-WIDGET-MAKER-001"
    assert len(prompts) >= 1
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()