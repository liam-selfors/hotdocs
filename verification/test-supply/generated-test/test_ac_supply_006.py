# hotdocs-criterion: sha256:944232033b4ab608a698f88c00221a7ede3d470017a473828bc080cc63357bb7
import hashlib
import json
from pathlib import Path

import test_supply


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE_TEXT = {
    "criterion_text": "c",
    "requirement_text": "r",
    "interface": "i",
    "glossary": "g",
    "testing": "",
}


def correct_header():
    payload = json.dumps(
        {k: BUNDLE_TEXT[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_assembler(repo_root):
    base = repo_root / "gen" / "spec-bundle-assembler"
    base.mkdir(parents=True, exist_ok=True)
    source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-FOO-001") + ",\n"
        "        'criterion_text': " + repr(BUNDLE_TEXT["criterion_text"]) + ",\n"
        "        'requirement_text': " + repr(BUNDLE_TEXT["requirement_text"]) + ",\n"
        "        'interface': " + repr(BUNDLE_TEXT["interface"]) + ",\n"
        "        'glossary': " + repr(BUNDLE_TEXT["glossary"]) + ",\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': " + repr(BUNDLE_TEXT["testing"]) + ",\n"
        "    }\n"
    )
    (base / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")


def write_probe_package(repo_root):
    pkg = repo_root / "gen" / "test-probe" / "test_probe"
    pkg.mkdir(parents=True, exist_ok=True)
    log_path = str(repo_root / "probe.log")
    source = (
        "import json\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.5.0'\n"
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
        "    with open(" + repr(log_path) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'module_name': module_name, 'kwargs': kwargs}, default=str) + '\\n')\n"
        "    return _Report()\n"
    )
    (pkg / "__init__.py").write_text(source, encoding="utf-8")


def make_author(repo_root):
    log_path = repo_root / "author.log"

    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "m",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "x", "content": correct_header() + "\n\ndef test_authored():\n    assert True\n"},
        }

    return author


def test_package_probe_used_for_current_committed_test(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_assembler(repo_root)
    write_probe_package(repo_root)

    committed_dir = repo_root / "verification" / "foo" / "generated-test"
    committed_dir.mkdir(parents=True)
    committed = committed_dir / "test_ac_foo_001.py"
    committed.write_text(
        correct_header() + "\n\nimport test_foo\n\n\ndef test_committed():\n    test_foo.run()\n",
        encoding="utf-8",
    )

    result = test_supply.supply("comp-foo", "AC-FOO-001", repo_root, test_author=make_author(repo_root))

    log = repo_root / "probe.log"
    assert log.is_file()
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1

    path = field(result, "path")
    assert path is not None
    assert Path(path).resolve() == committed.resolve()
    assert field(result, "failure_origin") is None