# hotdocs-criterion: sha256:33dfb6abda08ff4f810b7ead1ff1de1552274911ad82a1f1f505dddce0835601
import hashlib
import json
from pathlib import Path

import test_supply


BUNDLE_VALUES = {
    "criterion_text": "c",
    "requirement_text": "r",
    "interface": "i",
    "glossary": "g",
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def correct_header():
    text = json.dumps(
        {k: BUNDLE_VALUES[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_repo(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    assembler_dir = root / "gen" / "spec-bundle-assembler"
    assembler_dir.mkdir(parents=True, exist_ok=True)
    assembler_src = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-FOO-001") + ",\n"
        "        'criterion_text': " + repr(BUNDLE_VALUES["criterion_text"]) + ",\n"
        "        'requirement_text': " + repr(BUNDLE_VALUES["requirement_text"]) + ",\n"
        "        'interface': " + repr(BUNDLE_VALUES["interface"]) + ",\n"
        "        'glossary': " + repr(BUNDLE_VALUES["glossary"]) + ",\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': " + repr(BUNDLE_VALUES["testing"]) + ",\n"
        "    }\n"
    )
    (assembler_dir / "spec_bundle_assembler.py").write_text(assembler_src, encoding="utf-8")

    probe_dir = root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_log = str(root / "probe.log")
    probe_src = (
        "import json\n"
        "\n"
        "GATE_VERSION = " + repr("test-probe@1.5.0") + "\n"
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
    return root


def author_log_lines(root):
    log = Path(root) / "author.log"
    if not log.exists():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def result(model_call_error, content):
    return {
        "model": "m",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "model_call_error": model_call_error,
        "file": None if content is None else {"path": "x", "content": content},
    }


def make_author(root, responses):
    log = Path(root) / "author.log"
    calls = {"n": 0}

    def author(bundle):
        with open(log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        i = calls["n"]
        calls["n"] += 1
        return responses[min(i, len(responses) - 1)]

    return author


def good_content():
    return correct_header() + "\n\n\ndef test_placeholder():\n    assert True\n"


def test_transient_error_then_success(tmp_path):
    root = make_repo(tmp_path / "repo1")
    author = make_author(root, [
        result({"category": "network", "message": "dropped"}, None),
        result(None, good_content()),
    ])
    supplied = test_supply.supply("comp-foo", "AC-FOO-001", root, test_author=author)
    assert len(author_log_lines(root)) == 2
    assert field(supplied, "failure_origin") is None


def test_network_error_twice_fails(tmp_path):
    root = make_repo(tmp_path / "repo2")
    author = make_author(root, [result({"category": "network", "message": "dropped"}, None)])
    supplied = test_supply.supply("comp-foo", "AC-FOO-001", root, test_author=author)
    assert len(author_log_lines(root)) == 2
    assert field(supplied, "failure_message") == "test authoring failed: network: dropped"
    assert field(supplied, "failure_origin") == "test"
    assert field(supplied, "path") is None


def test_auth_error_fails_without_retry(tmp_path):
    root = make_repo(tmp_path / "repo3")
    author = make_author(root, [result({"category": "auth", "message": "bad key"}, None)])
    supplied = test_supply.supply("comp-foo", "AC-FOO-001", root, test_author=author)
    assert len(author_log_lines(root)) == 1
    assert field(supplied, "failure_message") == "test authoring failed: auth: bad key"
    assert field(supplied, "failure_origin") == "test"
    assert field(supplied, "path") is None


def test_no_test_author(tmp_path):
    root = make_repo(tmp_path / "repo4")
    supplied = test_supply.supply("comp-foo", "AC-FOO-001", root)
    assert field(supplied, "failure_message") == "test authoring failed: none: no test author"