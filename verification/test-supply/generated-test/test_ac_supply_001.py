# hotdocs-criterion: sha256:0f561fcc9ce7c7596d942342b018d078c9d3d8e94f4d9df624c44e90c13c45f5
import hashlib
import json
from pathlib import Path

import pytest

import test_supply


BUNDLE_TEXT = {
    "criterion_text": "c",
    "requirement_text": "r",
    "interface": "i",
    "glossary": "g",
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def correct_header():
    payload = json.dumps(
        {k: BUNDLE_TEXT[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


TEST_BODY = (
    "import foo\n"
    "\n"
    "\n"
    "def test_foo():\n"
    "    assert foo.run() is not None\n"
)


def write_stand_ins(repo_root):
    assembler_dir = repo_root / "gen" / "spec-bundle-assembler"
    assembler_dir.mkdir(parents=True)
    assembler_src = (
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
    (assembler_dir / "spec_bundle_assembler.py").write_text(assembler_src, encoding="utf-8")

    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    probe_log = str(repo_root / "probe.log")
    probe_src = (
        "import json\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.5.0'\n"
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(probe_log) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'module_name': module_name, 'kwargs': kwargs}, default=str) + '\\n')\n"
        "    return ProbeReport(True, [], 1, 1)\n"
    )
    (probe_dir / "test_probe.py").write_text(probe_src, encoding="utf-8")


def committed_path(repo_root):
    return repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_001.py"


def write_committed(repo_root, first_line):
    path = committed_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if first_line is None:
        content = TEST_BODY
    else:
        content = first_line + "\n" + TEST_BODY
    path.write_text(content, encoding="utf-8")
    return path


def make_author(repo_root, content):
    log = repo_root / "author.log"

    def stand_in(bundle):
        with open(log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "m",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "x", "content": content},
        }

    return stand_in


def test_current_committed_test_is_reused_without_authoring(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_stand_ins(repo_root)
    committed = write_committed(repo_root, correct_header())
    stand_in = make_author(repo_root, correct_header() + "\n" + TEST_BODY)

    result = test_supply.supply("comp-foo", "AC-FOO-001", repo_root, test_author=stand_in)

    path = field(result, "path")
    assert path is not None
    assert Path(path).resolve() == committed.resolve()
    assert field(result, "authored") is False
    assert field(result, "test_authoring") is None
    assert field(result, "failure_origin") is None
    assert not (repo_root / "author.log").exists()


@pytest.mark.parametrize(
    "first_line",
    [None, "# hotdocs-criterion: sha256:" + "0" * 64],
    ids=["no_header", "zero_hash_header"],
)
def test_stale_committed_test_is_authored_again(tmp_path, first_line):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_stand_ins(repo_root)
    write_committed(repo_root, first_line)
    returned = correct_header() + "\n" + TEST_BODY
    stand_in = make_author(repo_root, returned)

    result = test_supply.supply("comp-foo", "AC-FOO-001", repo_root, test_author=stand_in)

    log = repo_root / "author.log"
    assert log.exists()
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    assert field(result, "authored") is True

    path = field(result, "path")
    assert path is not None
    resolved = Path(path).resolve()
    assert resolved.is_file()
    verification = (repo_root / "verification").resolve()
    assert resolved != verification and verification not in resolved.parents
    assert resolved.read_text(encoding="utf-8") == returned