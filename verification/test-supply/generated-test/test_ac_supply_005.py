# hotdocs-criterion: sha256:0b9fac29cec3a041ee7c979f783a90af51ad644720ca5216cf30ba1579aa3977
import hashlib
import json
from pathlib import Path

import pytest

import test_supply


COMPONENT_ID = "comp-foo"
CRITERION_ID = "AC-FOO-001"

A = {"model": "m", "seed": 0, "prompt_version": "v1", "cache_hit": False}

TEST_BODY = (
    "import test_foo\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert test_foo.do_it() == 1\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundle_for(criterion_text):
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-FOO-001",
        "criterion_text": criterion_text,
        "requirement_text": "r",
        "interface": "i",
        "glossary": "g",
        "testing": "",
    }


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_assembler(repo_root, criterion_text):
    source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-001',\n"
        "        'criterion_text': " + repr(criterion_text) + ",\n"
        "        'requirement_text': 'r',\n"
        "        'interface': 'i',\n"
        "        'glossary': 'g',\n"
        "        'testing': '',\n"
        "    }\n"
    )
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", source)


def write_probe(repo_root, ok):
    log_path = str(repo_root / "probe.log")
    source = (
        "import json\n"
        "\n"
        "_LOG = " + repr(log_path) + "\n"
        "_OK = " + repr(bool(ok)) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self, ok, findings, tests_run, tests_reached):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = tests_run\n"
        "        self.tests_reached = tests_reached\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': [dict(f) for f in self.findings],\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'module_name': module_name, 'kwargs': kwargs}, default=str) + '\\n')\n"
        "    if _OK:\n"
        "        return _Report(True, [], 1, 1)\n"
        "    return _Report(False, [{'kind': 'test_bug', 'severity': 'error', 'line': 1,\n"
        "                            'message': 'test_something failed before reaching the code under test'}], 1, 0)\n"
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", source)


def committed_path(repo_root):
    return repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_001.py"


def make_author(repo_root, model_call_error, content):
    log_path = repo_root / "author.log"

    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("call\n")
        return {
            "model": "m",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": model_call_error,
            "file": None if content is None else {"path": "x", "content": content},
        }

    return author


def normalize_authoring(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    return {k: getattr(value, k) for k in ("model", "seed", "prompt_version", "cache_hit")}


CASES = [
    "current_committed_passing_probe",
    "no_committed_no_author",
    "author_always_auth_error",
    "author_file_probe_always_fails",
]


@pytest.mark.parametrize("case", CASES)
def test_authored_and_test_authoring_per_case(tmp_path, case):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_assembler(repo_root, "c")
    header = header_for(bundle_for("c"))

    if case == "current_committed_passing_probe":
        write_probe(repo_root, ok=True)
        write(committed_path(repo_root), header + "\n" + TEST_BODY)
        author = make_author(repo_root, None, header + "\n" + TEST_BODY)
        expected_authored, expected_authoring = False, None
    elif case == "no_committed_no_author":
        write_probe(repo_root, ok=True)
        author = None
        expected_authored, expected_authoring = False, None
    elif case == "author_always_auth_error":
        write_probe(repo_root, ok=True)
        author = make_author(repo_root, {"category": "auth", "message": "invalid api key"}, None)
        expected_authored, expected_authoring = True, A
    else:
        write_probe(repo_root, ok=False)
        author = make_author(repo_root, None, header + "\n" + TEST_BODY)
        expected_authored, expected_authoring = True, A

    result = test_supply.supply(COMPONENT_ID, CRITERION_ID, repo_root, test_author=author)

    assert field(result, "authored") is expected_authored
    assert normalize_authoring(field(result, "test_authoring")) == expected_authoring


def test_current_header_with_non_ascii_criterion_text_is_not_reauthored(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_assembler(repo_root, "caf\u00e9")
    write_probe(repo_root, ok=True)
    header = header_for(bundle_for("caf\u00e9"))
    write(committed_path(repo_root), header + "\n" + TEST_BODY)

    author = make_author(repo_root, None, header + "\n" + TEST_BODY)
    result = test_supply.supply(COMPONENT_ID, CRITERION_ID, repo_root, test_author=author)

    assert not (repo_root / "author.log").exists()
    assert field(result, "authored") is False