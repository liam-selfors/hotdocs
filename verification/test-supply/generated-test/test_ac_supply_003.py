# hotdocs-criterion: sha256:5ed4af64cedc3a88f1085adcc463a0677bd507eeb092667791142c173140f1f4
import hashlib
import json
from pathlib import Path

import test_supply


COMPONENT_ID = "comp-foo"
CRITERION_ID = "AC-FOO-001"
ASSETS = ["static/app.js"]
DRIVERS = ["browser"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-FOO-001",
        "criterion_text": "c",
        "requirement_text": "r",
        "interface": "i",
        "glossary": "g",
        "testing": "",
    }


def _header():
    bundle = _bundle()
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_assembler(repo_root):
    d = repo_root / "gen" / "spec-bundle-assembler"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-001',\n"
        "        'criterion_text': 'c',\n"
        "        'requirement_text': 'r',\n"
        "        'interface': 'i',\n"
        "        'glossary': 'g',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )
    (d / "spec_bundle_assembler.py").write_text(src, encoding="utf-8")


def _write_probe(repo_root, mode):
    d = repo_root / "gen" / "test-probe"
    d.mkdir(parents=True, exist_ok=True)
    log_path = str(repo_root / "probe.log")
    src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(log_path) + "\n"
        "MODE = " + repr(mode) + "\n"
        "MARKER = " + repr("COMMITTED_MARKER") + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self, ok, findings):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': [dict(f) for f in self.findings],\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def _finding(kind):\n"
        "    return {'kind': kind, 'severity': 'error', 'line': 1, 'message': kind + ' found'}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'module_name': module_name, 'kwargs': kwargs}, default=str) + '\\n')\n"
        "    if MODE == 'committed_fails':\n"
        "        if MARKER in test_source:\n"
        "            return _Report(False, [_finding('undefined_name')])\n"
        "        return _Report(True, [])\n"
        "    return _Report(False, [_finding('undefined_name'), _finding('syntax_error'),\n"
        "                           _finding('undefined_name')])\n"
    )
    (d / "test_probe.py").write_text(src, encoding="utf-8")


def _write_committed(repo_root):
    d = repo_root / "verification" / "foo" / "generated-test"
    d.mkdir(parents=True, exist_ok=True)
    content = (
        _header() + "\n"
        "# COMMITTED_MARKER\n"
        "def test_committed():\n"
        "    assert True\n"
    )
    (d / "test_ac_foo_001.py").write_text(content, encoding="utf-8")


def _make_author(repo_root):
    log_path = repo_root / "author.log"
    content = (
        _header() + "\n"
        "# AUTHORED\n"
        "def test_authored():\n"
        "    assert True\n"
    )

    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "m",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "x", "content": content},
        }

    return author


def _lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_committed_test_failing_probe_is_authored_once_and_probe_gets_assets_drivers(tmp_path):
    repo_root = tmp_path
    _write_assembler(repo_root)
    _write_probe(repo_root, "committed_fails")
    _write_committed(repo_root)
    author = _make_author(repo_root)

    result = test_supply.supply(
        COMPONENT_ID, CRITERION_ID, repo_root,
        test_author=author, assets=list(ASSETS), drivers=list(DRIVERS),
    )

    assert len(_lines(repo_root / "author.log")) == 1
    assert field(result, "authored") is True
    assert field(result, "failure_origin") is None

    probe_lines = _lines(repo_root / "probe.log")
    assert len(probe_lines) >= 1
    for line in probe_lines:
        entry = json.loads(line)
        assert entry["module_name"] == "foo"
        assert list(entry["kwargs"]["assets"]) == ASSETS
        assert list(entry["kwargs"]["drivers"]) == DRIVERS


def test_authored_test_still_failing_probe_gives_test_failure(tmp_path):
    repo_root = tmp_path
    _write_assembler(repo_root)
    _write_probe(repo_root, "always_fails")
    _write_committed(repo_root)
    author = _make_author(repo_root)

    result = test_supply.supply(
        COMPONENT_ID, CRITERION_ID, repo_root,
        test_author=author, assets=list(ASSETS), drivers=list(DRIVERS),
    )

    assert len(_lines(repo_root / "author.log")) == 1
    assert field(result, "failure_origin") == "test"
    assert field(result, "path") is None
    assert field(result, "failure_message") == "test failed its probe: undefined_name, syntax_error"