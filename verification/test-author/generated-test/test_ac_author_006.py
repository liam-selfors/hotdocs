# hotdocs-criterion: sha256:db60a38a6d29476554349d30e5b8a759743c0c6a8852730c74001b2e10a2038b
import re
from pathlib import Path, PurePosixPath

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
CRITERION_ID = "AC-WIDGET-MAKER-001"
EXPECTED_REL = "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"

MOCK_TEST = "def test_widget():\n    assert True\n"


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
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _mock_backend(prompt, model, **params):
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    text = (
        "-----BEGIN FILE " + nonce + "-----\n"
        + MOCK_TEST
        + "\n-----END FILE " + nonce + "-----"
    )
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def _bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _relative(path_value, repo_root):
    p = Path(str(path_value))
    if p.is_absolute():
        p = p.resolve().relative_to(Path(repo_root).resolve())
    return PurePosixPath(p.as_posix())


def test_author_test_writes_only_under_generated_test_dir(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    result = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=_mock_backend
    )

    assert field(result, "model_call_error") is None
    assert log_path.is_file() and log_path.read_text(encoding="utf-8").strip() != ""

    file_info = field(result, "file")
    assert file_info is not None
    rel = _relative(field(file_info, "path"), repo_root)

    # Under verification/<component>/generated-test/, directly, with D63 filename.
    assert str(rel) == EXPECTED_REL
    assert rel.parts[:3] == ("verification", SLUG, "generated-test")
    assert len(rel.parts) == 4
    assert rel.name == "test_ac_widget_maker_001.py"

    # Not under gen/<component>/ nor criterion-compiler's output directory.
    assert rel.parts[0] != "gen"
    assert rel.parts[:3] != ("verification", SLUG, "compiled")

    written = repo_root / Path(*rel.parts)
    assert written.is_file()

    # Nothing written under gen/<component>/ or the compiled directory.
    assert not (repo_root / "gen" / SLUG).exists()
    assert not (repo_root / "gen" / COMPONENT_ID).exists()
    assert not (repo_root / "verification" / SLUG / "compiled").exists()

    # The only file under verification/ is the expected generated test.
    verification_files = sorted(
        PurePosixPath(p.relative_to(repo_root).as_posix())
        for p in (repo_root / "verification").rglob("*")
        if p.is_file()
    )
    assert [str(p) for p in verification_files] == [EXPECTED_REL]

    # Nothing new under gen/ besides the test-probe stand-in.
    gen_files = sorted(
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / "gen").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    assert gen_files == ["gen/test-probe/test_probe.py"]