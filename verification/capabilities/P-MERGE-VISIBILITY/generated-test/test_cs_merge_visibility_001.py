# hotdocs-criterion: sha256:0a04f6db239ceccc768750076dbab95aced0e3bb863656bd55ec301fc32681e5
"""CS-MERGE-VISIBILITY-001: merge status is visible and recoverable.

A change touches three components: two generate and verify, one fails
verification. A developer queries provenance-tracker (check_readiness /
`hotdocs verify`) afresh after each step and sees, per component, whether
it is ready and why not. After a spec edit to the failing component and a
second generation of it alone, the two unchanged components are still
ready (provenance hits, never regenerated), alongside the third's fresh
passing result, with no reliance on the first run's CLI output.
"""

import importlib.util
import json
import sys
from pathlib import Path

import provenance_tracker
import provenance_tracker_ui  # noqa: F401  (imported per the bundle's module list)


COMPONENTS = ["comp-alpha", "comp-beta", "comp-gamma"]
FAILING = "comp-gamma"
READY_PAIR = ["comp-alpha", "comp-beta"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def opt_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(
        p for p in Path(provenance_tracker.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    return load_module(path, "spec_linter")


def assert_lint_clean(repo_root):
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


# --------------------------------------------------------------------------
# Fixture corpus
# --------------------------------------------------------------------------

def slug_of(component_id):
    return component_id[len("comp-"):]


def rid_of(component_id):
    return "R-" + slug_of(component_id).upper() + "-001"


def acid_of(component_id):
    return "AC-" + slug_of(component_id).upper() + "-001"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n"
        "- **Widget** - a value a fixture component returns.\n",
    )
    for cid in COMPONENTS:
        slug = slug_of(cid)
        base = repo_root / "specs" / "components" / slug
        write(
            base / "component.md",
            "---\n"
            "id: " + cid + "\n"
            "title: Fixture " + slug + "\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "sealed: true\n"
            "source_path: legacy/" + slug + "/\n"
            "---\n\n"
            "# Fixture " + slug + "\n\n"
            "## Purpose\n\n"
            "A fixture component used to exercise merge visibility.\n",
        )
        rid = rid_of(cid)
        write(
            base / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n"
            "The component MUST return a widget.\n",
        )
        acid = acid_of(cid)
        write(
            base / "acceptance" / (acid + ".md"),
            "# " + acid + "\n\n"
            "Covers: " + rid + "\n"
            "Kind: generated-test\n\n"
            "```gherkin\n"
            "Given the component\n"
            "When it is called\n"
            "Then it returns a widget\n"
            "```\n",
        )


def edit_failing_spec(repo_root):
    rid = rid_of(FAILING)
    path = (
        repo_root / "specs" / "components" / slug_of(FAILING)
        / "requirements" / (rid + ".md")
    )
    write(
        path,
        "# " + rid + "\n\n"
        "The component MUST return a widget, and MUST return it unchanged.\n",
    )


# --------------------------------------------------------------------------
# Fake dependencies (flat-module shape under the temporary repo_root)
# --------------------------------------------------------------------------

def write_state(state_path, state):
    state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")


def write_fake_provenance_checker(repo_root, state_path, log_path):
    src = (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "STATE = " + repr(str(state_path)) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "IDS = " + repr(list(COMPONENTS)) + "\n"
        "KEY_PREFIX = 'sha256:fake-'\n"
        "\n"
        "def _state():\n"
        "    return json.loads(Path(STATE).read_text(encoding='utf-8'))\n"
        "\n"
        "def _log(name, cid):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + ' ' + str(cid) + '\\n')\n"
        "\n"
        "def _match(value):\n"
        "    if isinstance(value, dict):\n"
        "        for k in ('component_id', 'id', 'key'):\n"
        "            if k in value:\n"
        "                found = _match(value[k])\n"
        "                if found:\n"
        "                    return found\n"
        "        return None\n"
        "    for attr in ('component_id', 'key'):\n"
        "        inner = getattr(value, attr, None)\n"
        "        if isinstance(inner, str):\n"
        "            found = _match(inner)\n"
        "            if found:\n"
        "                return found\n"
        "    if not isinstance(value, str):\n"
        "        return None\n"
        "    for cid in IDS:\n"
        "        if value == cid or value.startswith(KEY_PREFIX + cid + '-v'):\n"
        "            return cid\n"
        "    return None\n"
        "\n"
        "def _find(args, kwargs):\n"
        "    for v in list(args) + list(kwargs.values()):\n"
        "        found = _match(v)\n"
        "        if found:\n"
        "            return found\n"
        "    return None\n"
        "\n"
        "def _key(cid):\n"
        "    return KEY_PREFIX + cid + '-v' + str(_state()[cid]['version'])\n"
        "\n"
        "def _result(cid):\n"
        "    entry = _state()[cid]\n"
        "    key = _key(cid)\n"
        "    if not entry['hit']:\n"
        "        return {\n"
        "            'component_id': cid,\n"
        "            'hit': False,\n"
        "            'key': key,\n"
        "            'reason': 'no provenance for current spec state',\n"
        "            'manifest': None,\n"
        "            'verification_report': None,\n"
        "            'license_scan': None,\n"
        "            'secret_scan': None,\n"
        "        }\n"
        "    return {\n"
        "        'component_id': cid,\n"
        "        'hit': True,\n"
        "        'key': key,\n"
        "        'reason': None,\n"
        "        'manifest': {'component_id': cid, 'spec_bundle_hash': key},\n"
        "        'verification_report': {\n"
        "            'component_id': cid,\n"
        "            'overall': entry['overall'],\n"
        "            'requirement_results': {entry['rid']: entry['overall']},\n"
        "            'criteria': [],\n"
        "        },\n"
        "        'license_scan': {'blocked': False, 'findings': []},\n"
        "        'secret_scan': {'flagged': False, 'matches': []},\n"
        "    }\n"
        "\n"
        "def current_sealed_key(*args, **kwargs):\n"
        "    cid = _find(args, kwargs)\n"
        "    _log('current_sealed_key', cid)\n"
        "    if cid is None:\n"
        "        return None\n"
        "    return _key(cid)\n"
        "\n"
        "def current_provenance_key(*args, **kwargs):\n"
        "    cid = _find(args, kwargs)\n"
        "    _log('current_provenance_key', cid)\n"
        "    if cid is None:\n"
        "        return None\n"
        "    return _key(cid)\n"
        "\n"
        "def check_provenance(*args, **kwargs):\n"
        "    cid = _find(args, kwargs)\n"
        "    _log('check_provenance', cid)\n"
        "    return _result(cid)\n"
        "\n"
        "def check_sealed_provenance(*args, **kwargs):\n"
        "    cid = _find(args, kwargs)\n"
        "    _log('check_sealed_provenance', cid)\n"
        "    return _result(cid)\n"
    )
    write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", src)


def write_fake_secret_scanner(repo_root, log_path):
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('scan ' + str(repo_root) + '\\n')\n"
        "    return {'flagged': False, 'matches': []}\n"
    )
    write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", src)


# --------------------------------------------------------------------------
# Simulated `hotdocs generate` attempts (component-gate-runner's call)
# --------------------------------------------------------------------------

def record_attempt(repo_root, cid, overall, key):
    rid = rid_of(cid)
    generation = {
        "component_id": cid,
        "files": ["gen/" + slug_of(cid) + "/" + slug_of(cid).replace("-", "_") + ".py"],
        "model": "anthropic:claude-sonnet-5",
        "model_call_error": None,
    }
    verification = {
        "component_id": cid,
        "overall": overall,
        "requirement_results": {rid: overall},
        "criteria": [
            {
                "criterion_id": acid_of(cid),
                "covers": rid,
                "result": overall,
            }
        ],
    }
    return provenance_tracker.write_attempt_record(
        cid, generation, verification, key, repo_root
    )


def attempt_files(repo_root, cid):
    d = repo_root / ".hotdocs" / "attempts" / cid
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.glob("*.json"))


# --------------------------------------------------------------------------
# Readiness helpers
# --------------------------------------------------------------------------

def component_ready(result):
    if not field(result, "hit"):
        return False
    report = opt_field(result, "verification_report")
    if report is None:
        return False
    if opt_field(report, "overall") != "pass":
        return False
    license_scan = opt_field(result, "license_scan")
    if license_scan is not None and opt_field(license_scan, "blocked", False):
        return False
    return True


def run_verify_cli(repo_root, capsys):
    capsys.readouterr()
    try:
        code = provenance_tracker.main(
            ["verify", "--repo-root", str(repo_root), "--format=json"]
        )
    except SystemExit as exc:
        code = exc.code
    out = capsys.readouterr().out
    return (0 if code is None else code), out


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------

def test_cs_merge_visibility_001(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_path = tmp_path / "fake_state.json"
    checker_log = tmp_path / "checker.log"
    scanner_log = tmp_path / "scanner.log"
    checker_log.write_text("", encoding="utf-8")
    scanner_log.write_text("", encoding="utf-8")

    build_corpus(repo_root)
    write_fake_provenance_checker(repo_root, state_path, checker_log)
    write_fake_secret_scanner(repo_root, scanner_log)

    # Given: the corpus passes lint.
    assert_lint_clean(repo_root)

    # Step 1: the change touches three components. Two generate and
    # verify (provenance written, passing); the third fails verification
    # (no provenance for its spec state).
    state = {
        "comp-alpha": {"version": 1, "hit": True, "overall": "pass", "rid": rid_of("comp-alpha")},
        "comp-beta": {"version": 1, "hit": True, "overall": "pass", "rid": rid_of("comp-beta")},
        "comp-gamma": {"version": 1, "hit": False, "overall": "fail", "rid": rid_of("comp-gamma")},
    }
    write_state(state_path, state)
    for cid in READY_PAIR:
        record_attempt(repo_root, cid, "pass", "sha256:fake-" + cid + "-v1")
    record_attempt(repo_root, FAILING, "fail", "sha256:fake-" + FAILING + "-v1")

    assert_lint_clean(repo_root)

    # First query: a fresh, live answer from provenance-tracker.
    report1 = provenance_tracker.check_readiness(repo_root)
    comps1 = field(report1, "components")
    for cid in COMPONENTS:
        assert cid in comps1, "component missing from first report: " + cid
    ready1 = sorted(cid for cid in COMPONENTS if component_ready(comps1[cid]))
    not_ready1 = sorted(cid for cid in COMPONENTS if not component_ready(comps1[cid]))
    assert ready1 == sorted(READY_PAIR)
    assert not_ready1 == [FAILING]
    assert field(report1, "ready") is False

    reasons1 = list(field(report1, "not_ready_reasons"))
    assert any(FAILING in r for r in reasons1), reasons1
    for cid in READY_PAIR:
        assert not any(cid in r for r in reasons1), reasons1

    # The failing component's reason is recoverable without the first
    # run's CLI output: its failing R-id is available from tracking data.
    assert list(provenance_tracker.last_requirement_failures(FAILING, repo_root)) == [
        rid_of(FAILING)
    ]
    for cid in READY_PAIR:
        assert list(provenance_tracker.last_requirement_failures(cid, repo_root)) == []

    code1, out1 = run_verify_cli(repo_root, capsys)
    assert code1 == 1
    cli_report1 = json.loads(out1)
    assert cli_report1["ready"] is False
    assert any(FAILING in r for r in cli_report1["not_ready_reasons"])

    attempts_after_step1 = {cid: attempt_files(repo_root, cid) for cid in COMPONENTS}
    for cid in COMPONENTS:
        assert len(attempts_after_step1[cid]) == 1, (cid, attempts_after_step1[cid])

    # Step 2: a spec edit to the failing component, then a second
    # `hotdocs generate` of it alone, which now verifies.
    edit_failing_spec(repo_root)
    assert_lint_clean(repo_root)
    state[FAILING] = {"version": 2, "hit": True, "overall": "pass", "rid": rid_of(FAILING)}
    write_state(state_path, state)
    record_attempt(repo_root, FAILING, "pass", "sha256:fake-" + FAILING + "-v2")

    # Second query, again fresh.
    report2 = provenance_tracker.check_readiness(repo_root)
    comps2 = field(report2, "components")
    for cid in COMPONENTS:
        assert cid in comps2, "component missing from second report: " + cid

    # The two unchanged components are still ready, as provenance hits.
    for cid in READY_PAIR:
        assert field(comps2[cid], "hit") is True
        assert component_ready(comps2[cid])
        key1 = opt_field(comps1[cid], "key")
        key2 = opt_field(comps2[cid], "key")
        if key1 is not None and key2 is not None:
            assert key1 == key2

    # ...and were never regenerated: no new attempt for either.
    for cid in READY_PAIR:
        assert attempt_files(repo_root, cid) == attempts_after_step1[cid]

    # The third shows its fresh result.
    assert field(comps2[FAILING], "hit") is True
    assert component_ready(comps2[FAILING])
    assert len(attempt_files(repo_root, FAILING)) == 2
    assert list(provenance_tracker.last_requirement_failures(FAILING, repo_root)) == []

    assert field(report2, "ready") is True
    reasons2 = list(field(report2, "not_ready_reasons"))
    assert not any(cid in r for cid in COMPONENTS for r in reasons2), reasons2

    code2, out2 = run_verify_cli(repo_root, capsys)
    assert code2 == 0
    cli_report2 = json.loads(out2)
    assert cli_report2["ready"] is True
    for cid in COMPONENTS:
        assert cli_report2["components"][cid]["hit"] is True

    # The fake checker was actually consulted for every component.
    logged = checker_log.read_text(encoding="utf-8").splitlines()
    for cid in COMPONENTS:
        assert any(line.endswith(" " + cid) for line in logged), (cid, logged)