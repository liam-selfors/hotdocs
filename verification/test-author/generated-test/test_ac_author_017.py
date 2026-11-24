# hotdocs-criterion: sha256:9838b24905dcd4b6677f68998bd851246b05f5cdad92c0c3725843685f355a12
import re

import test_author


EXPECTED_TEST = "import test_author\n\n\ndef test_placeholder():\n    assert test_author is not None\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def mock_backend(prompt, model, **params):
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


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


BASE_FIELDS = {
    "component_id": "comp-widget-maker",
    "criterion_id": "AC-WIDGET-MAKER-001",
    "covers": "R-WIDGET-MAKER-001",
    "criterion_text": "Given a widget When made Then it exists",
    "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be makeable",
    "interface": "make_widget() -> dict",
    "glossary": "",
}


class PlainBundle:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def check_completed(result, repo_root, log_path):
    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    path = file["path"]
    assert path == "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"
    assert body(file["content"]) == EXPECTED_TEST
    written = repo_root / path
    assert written.is_file()
    assert body(written.read_text(encoding="utf-8")) == EXPECTED_TEST
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1


def test_object_bundle_without_dependency_interfaces_attribute(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_obj"
    repo_root.mkdir()
    log_path = tmp_path / "probe_obj.log"
    write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    bundle = PlainBundle(**BASE_FIELDS)
    assert not isinstance(bundle, dict)
    assert not hasattr(bundle, "dependency_interfaces")

    try:
        result = test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
        )
    except AttributeError as exc:
        raise AssertionError(
            "author_test raised AttributeError for missing dependency_interfaces: " + repr(exc)
        )

    check_completed(result, repo_root, log_path)


def test_dict_bundle_without_dependency_interfaces_key(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_dict"
    repo_root.mkdir()
    log_path = tmp_path / "probe_dict.log"
    write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    bundle = dict(BASE_FIELDS)
    assert "dependency_interfaces" not in bundle

    try:
        result = test_author.author_test(
            bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
        )
    except KeyError as exc:
        raise AssertionError(
            "author_test raised KeyError for missing dependency_interfaces: " + repr(exc)
        )

    check_completed(result, repo_root, log_path)