# hotdocs-criterion: sha256:2b035f8dbdc356ce0cb8e88a854be98c8cd1bdf16afac2f3fa71b4ae308c7699
import re

import pytest

import test_author


TEST_BODY = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def mock_backend(prompt, model, **params):
    n = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    text = "-----BEGIN FILE " + n + "-----\n" + TEST_BODY + "\n-----END FILE " + n + "-----"
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as f:\n"
        "        f.write('called\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return root


class _ObjectBundle:
    """A CriterionBundle-shaped plain object with no dependency_interfaces attribute."""

    def __init__(self):
        self.component_id = "comp-widget-maker"
        self.criterion_id = "AC-WIDGET-MAKER-001"
        self.covers = "R-WIDGET-MAKER-001"
        self.criterion_text = "Given a widget\nWhen make is called\nThen it returns a widget"
        self.requirement_text = "R-WIDGET-MAKER-001 make() MUST return a widget."
        self.interface = "make() -> Widget"
        self.glossary = ""


def assert_completed(result, repo_root, log_path):
    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    assert body(field(file, "content")) == TEST_BODY
    expected_path = "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"
    assert field(file, "path") == expected_path
    written = repo_root / expected_path
    assert written.is_file()
    assert body(written.read_text(encoding="utf-8")) == TEST_BODY
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("called") >= 1


def test_object_bundle_without_dependency_interfaces_attribute(repo_root, tmp_path):
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    bundle = _ObjectBundle()
    assert not hasattr(bundle, "dependency_interfaces")
    assert not isinstance(bundle, dict)

    try:
        result = test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
        )
    except AttributeError as exc:  # pragma: no cover - failure path
        pytest.fail("author_test raised AttributeError: " + repr(exc))

    assert_completed(result, repo_root, log_path)


def test_dict_bundle_missing_dependency_interfaces_key(repo_root, tmp_path):
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen make is called\nThen it returns a widget",
        "requirement_text": "R-WIDGET-MAKER-001 make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
    }
    assert "dependency_interfaces" not in bundle

    try:
        result = test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
        )
    except KeyError as exc:  # pragma: no cover - failure path
        pytest.fail("author_test raised KeyError: " + repr(exc))

    assert_completed(result, repo_root, log_path)