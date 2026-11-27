# hotdocs-criterion: sha256:d04c6618e435aaffeb721312c5ffe84cd80a1b72c29451cd9eb6ce19df8f0a41
"""AC-GEN-004: the model identifier passed to `generate` reaches the model unchanged.

Given the same SpecBundle and two different model identifiers
When generate is called once with each
Then the mock model recorded for each call receives the model identifier
  passed to that call, not a hardcoded default
"""

import json
import re
from pathlib import Path

import generator


PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"python\"\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [\"bad.py:1: SyntaxError: x\"] if (Path(code_dir) / \"bad.py\").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A mapping with the SpecBundle fields that also reads by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make_widget() -> str",
        constraints="No network.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="A widget is a thing.",
        hint_code=None,
        spec_bundle_parts={},
    )


def make_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    adapter = root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def make_mock(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        reply = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 'widget'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)["model"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_model_identifier_passed_through_to_mock_model(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    make_repo(repo_root)
    monkeypatch.chdir(tmp_path)

    bundle = make_bundle()
    model_a = "model-alpha-test-1"
    model_b = "model-beta-test-2"

    log_a = tmp_path / "log_a.jsonl"
    log_b = tmp_path / "log_b.jsonl"

    result_a = generator.generate(
        bundle, model_a, repo_root=repo_root, llm_backend=make_mock(log_a)
    )
    result_b = generator.generate(
        bundle, model_b, repo_root=repo_root, llm_backend=make_mock(log_b)
    )

    calls_a = read_log(log_a)
    calls_b = read_log(log_b)

    assert calls_a, "mock model was never called for the first generate call"
    assert calls_b, "mock model was never called for the second generate call"
    assert all(m == model_a for m in calls_a), calls_a
    assert all(m == model_b for m in calls_b), calls_b

    assert field(result_a, "cache_hit") is False
    assert field(result_b, "cache_hit") is False
    assert field(result_a, "model_call_error") is None
    assert field(result_b, "model_call_error") is None
    assert field(result_a, "refused") is None
    assert field(result_b, "refused") is None
    assert field(result_a, "model") == model_a
    assert field(result_b, "model") == model_b