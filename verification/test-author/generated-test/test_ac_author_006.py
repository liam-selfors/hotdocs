# hotdocs-criterion: sha256:843d74901ed9058753156281f537ec40ad7d80fa04bd316605ea87aef9633a58
import re
from pathlib import Path, PurePosixPath

import test_author


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
CRITERION_ID = "AC-WIDGET-MAKER-001"
EXPECTED_REL = "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"

GOOD_TEST = "import widget_maker\n\n\ndef test_widget():\n    assert widget_maker.make() is not None\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget When made Then it exists",
        "requirement_text": "R-WIDGET-MAKER-001 A widget MUST be made.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe_stand_in(repo_root, log_path):
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def mock_backend(prompt, model, **params):
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    text = (
        "-----BEGIN FILE " + nonce + "-----\n"
        + GOOD_TEST
        + "\n-----END FILE " + nonce + "-----"
    )
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def all_files(root):
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def test_written_file_is_under_verification_generated_test_only(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    gen_before = set(all_files(repo_root / "gen"))

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    # Precondition: a successful call.
    assert field(result, "model_call_error") is None
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("probe\n") >= 1

    file_entry = field(result, "file")
    assert file_entry is not None
    rel = field(file_entry, "path")
    rel_posix = PurePosixPath(str(rel).replace("\\", "/"))

    # The path is relative to repo_root and is exactly under verification/<slug>/generated-test/.
    assert not rel_posix.is_absolute()
    assert str(rel_posix) == EXPECTED_REL
    parts = rel_posix.parts
    assert len(parts) == 4
    assert parts[0] == "verification"
    assert parts[1] == SLUG
    assert parts[2] == "generated-test"
    assert parts[3] == "test_ac_widget_maker_001.py"

    # Not under gen/<component>/, nor under criterion-compiler's own output directory.
    assert parts[0] != "gen"
    assert "compiled" not in parts
    assert not str(rel_posix).startswith("gen/")
    assert not str(rel_posix).startswith("verification/" + SLUG + "/compiled")

    # The file really was written there.
    written = repo_root / Path(*parts)
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == field(file_entry, "content")

    # Nothing else was written under verification/: exactly the one file.
    verification_files = all_files(repo_root / "verification")
    assert verification_files == [written]

    # Nothing written under gen/<component>/ or criterion-compiler's directory.
    assert all_files(repo_root / "gen" / SLUG) == []
    assert not (repo_root / "gen" / SLUG).exists()
    assert not (repo_root / "verification" / SLUG / "compiled").exists()
    gen_after = set(all_files(repo_root / "gen"))
    new_gen_files = [p for p in gen_after - gen_before if p.suffix != ".pyc"]
    assert new_gen_files == []