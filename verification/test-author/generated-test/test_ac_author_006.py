# hotdocs-criterion: sha256:714985c25761bea5b6c2bf8930a725192e98462cc8142cc3524a4ae6adb2e7d5
import os
import re
from pathlib import Path, PurePosixPath

import test_author


COMPONENT_ID = "comp-widget-maker"
CRITERION_ID = "AC-WIDGET-MAKER-001"
SLUG = "widget-maker"
EXPECTED_REL = "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"

TEST_BODY = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make_widget() is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "GATE_VERSION = " + repr("test-probe@1.3.0") + "\n"
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
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport(True, [], 1, 1)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _mock_backend(prompt, model, **params):
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    text = (
        "-----BEGIN FILE " + nonce + "-----\n"
        + TEST_BODY
        + "\n-----END FILE " + nonce + "-----"
    )
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given a widget maker\n"
            "When make_widget is called\n"
            "Then it returns a widget"
        ),
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _relative_posix(path_value, repo_root):
    p = Path(str(path_value))
    if p.is_absolute():
        p = p.resolve().relative_to(repo_root.resolve())
    return PurePosixPath(p.as_posix())


def test_output_written_only_under_generated_test_dir(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    result = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=_mock_backend
    )

    assert field(result, "model_call_error") is None
    file_info = field(result, "file")
    assert file_info is not None
    path_value = field(file_info, "path")

    rel = _relative_posix(path_value, repo_root)

    # Exact path: verification/<slug>/generated-test/<criterion test filename>
    assert str(rel) == EXPECTED_REL
    assert rel.parent == PurePosixPath("verification", SLUG, "generated-test")
    assert rel.name == "test_ac_widget_maker_001.py"

    # Not under gen/<component>/ nor under gen/ at all.
    assert rel.parts[0] != "gen"
    # Not under criterion-compiler's own output directory.
    assert PurePosixPath("verification", SLUG, "compiled") not in rel.parents
    assert "compiled" not in rel.parts

    # The file actually exists where the path says.
    written = repo_root / EXPECTED_REL
    assert written.is_file()

    # The probe stand-in ran.
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("probe\n") >= 1

    # Nothing was written under gen/<component>/ or the compiled directory.
    assert not (repo_root / "gen" / SLUG).exists()
    assert not (repo_root / "verification" / SLUG / "compiled").exists()

    # The only file under verification/ is the generated test.
    files_under_verification = sorted(
        PurePosixPath(p.relative_to(repo_root).as_posix())
        for p in (repo_root / "verification").rglob("*")
        if p.is_file()
    )
    assert files_under_verification == [PurePosixPath(EXPECTED_REL)]

    # gen/ holds only the test-probe stand-in we planted.
    gen_files = sorted(
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / "gen").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    assert gen_files == ["gen/test-probe/test_probe.py"]