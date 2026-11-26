# hotdocs-criterion: sha256:ad7926e826ab1df2ee66616ee6b43de618553f5436c0d52be72e81d038db8a9e
import re
from pathlib import Path

import test_author


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
CRITERION_ID = "AC-WIDGET-MAKER-001"
EXPECTED_FILENAME = "test_ac_widget_maker_001.py"

GOOD_TEST = "import widget_maker\n\n\ndef test_it():\n    assert widget_maker.make() is not None\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def _bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _write_probe_stand_in(repo_root, log_path):
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _mock_backend(prompt, model, **params):
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    text = (
        "-----BEGIN FILE " + nonce + "-----\n"
        + GOOD_TEST
        + "\n-----END FILE " + nonce + "-----"
    )
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _files_under(path):
    if not path.exists():
        return set()
    return {p.resolve() for p in path.rglob("*") if p.is_file()}


def test_written_file_is_only_under_generated_test_dir(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    gen_before = _files_under(repo_root / "gen")

    result = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=_mock_backend
    )

    assert field(result, "model_call_error") is None
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("probe\n") >= 1

    file = field(result, "file")
    assert file is not None
    rel_path = field(file, "path")
    assert isinstance(rel_path, str)

    # The reported path is exactly the generated-test location with the glossary filename.
    expected_rel = "verification/" + SLUG + "/generated-test/" + EXPECTED_FILENAME
    assert Path(rel_path).as_posix() == expected_rel

    written = (repo_root / rel_path).resolve()
    assert written.is_file()

    generated_dir = (repo_root / "verification" / SLUG / "generated-test").resolve()
    # Directly under generated-test/, no further nesting.
    assert written.parent == generated_dir
    assert written.name == EXPECTED_FILENAME

    # Not under gen/<component>/ (nor anywhere under gen/).
    gen_root = (repo_root / "gen").resolve()
    assert gen_root not in written.parents
    assert not (repo_root / "gen" / SLUG).exists() or not _files_under(repo_root / "gen" / SLUG)
    assert _files_under(repo_root / "gen") == gen_before

    # Not under criterion-compiler's own output directory.
    compiled_dir = (repo_root / "verification" / SLUG / "compiled").resolve()
    assert compiled_dir not in written.parents
    assert not _files_under(repo_root / "verification" / SLUG / "compiled")

    # The only file written under verification/ is this one.
    assert _files_under(repo_root / "verification") == {written}

    # The written file holds the returned content, whose body is the model's file.
    content = field(file, "content")
    assert written.read_text(encoding="utf-8") == content
    assert body(content) == GOOD_TEST