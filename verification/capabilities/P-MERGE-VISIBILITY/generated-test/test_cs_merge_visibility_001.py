# hotdocs-criterion: sha256:31e3b0d33cf9cc21e6f40ef959562c4854a7bd0ee2beb89bbe500476cce08509
"""CS-MERGE-VISIBILITY-001: merge status is visible and recoverable.

Three components are touched by a change. Two generate and verify and one
fails verification. Querying provenance-tracker shows two ready and one not
ready, with its reason. After a spec edit to the failing component and a
second generate of only that component, the next query shows the two
unchanged components still ready as provenance hits (not regenerated)
alongside the third's fresh, passing result. Every answer comes from a live
query, never from a kept copy of an earlier run's CLI output.
"""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import provenance_tracker
import provenance_tracker_ui  # noqa: F401  (imported as the bundle states)
import ui_style  # noqa: F401  (imported as the bundle states)


COMPONENTS = ["comp-alpha", "comp-beta", "comp-gamma"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(p for p in Path(provenance_tracker.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def assert_lint_clean(repo_root):
    spec_linter = load_spec_linter()
    result = spec_linter.lint(None, repo_root)
    assert field(result, "hard_failures") == 0


# ---------------------------------------------------------------- fixture


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def requirement_text(rid, body):
    return "# " + rid + "\n\n" + body + "\n"


def acceptance_text(acid, rid, body):
    return (
        "# " + acid + "\n\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n" + body + "\n```\n"
    )


def build_component(repo_root, slug, prefix, requirements):
    base = repo_root / "specs" / "components" / slug
    title = slug.capitalize()
    write(
        base / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n\n"
        "# " + title + "\n\n"
        "## Purpose\n\n"
        + title + " returns a short greeting for its caller.\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\n```\ngreet() -> str\n```\n\nReturns a short greeting.\n",
    )
    for number, body in requirements:
        rid = "R-" + prefix + "-" + number
        acid = "AC-" + prefix + "-" + number
        write(base / "requirements" / (rid + ".md"), requirement_text(rid, body))
        write(
            base / "acceptance" / (acid + ".md"),
            acceptance_text(
                acid,
                rid,
                "Given the component\nWhen greet() is called\nThen it returns a non-empty string",
            ),
        )
    write(repo_root / "legacy" / slug / (slug + ".py"), "def greet():\n    return 'hello'\n")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Greeting** — a short, non-empty string a component returns.\n",
    )
    build_component(repo_root, "alpha", "ALPHA", [("001", "The component MUST return a greeting.")])
    build_component(repo_root, "beta", "BETA", [("001", "The component MUST return a greeting.")])
    build_component(
        repo_root,
        "gamma",
        "GAMMA",
        [
            ("001", "The component MUST return a greeting."),
            ("002", "The greeting MUST be at most ten characters long."),
        ],
    )


def component_key(repo_root, component_id):
    slug = component_id[len("comp-"):]
    base = repo_root / "specs" / "components" / slug
    h = hashlib.sha256()
    for p in sorted(base.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(base)).encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return "sha256:" + h.hexdigest()


FAKE_CHECKER_BODY = "\n".join([
    "import hashlib",
    "import json",
    "",
    "",
    "def _log(name):",
    "    with open(LOG, 'a', encoding='utf-8') as f:",
    "        f.write(name + '\\n')",
    "",
    "",
    "def _scan(value, found, depth=0):",
    "    if depth > 4:",
    "        return",
    "    if isinstance(value, str):",
    "        if value in COMPONENTS:",
    "            found.append(value)",
    "        elif ('comp-' + value) in COMPONENTS:",
    "            found.append('comp-' + value)",
    "        return",
    "    if isinstance(value, dict):",
    "        cid = value.get('component_id')",
    "        if isinstance(cid, str):",
    "            _scan(cid, found, depth + 1)",
    "        for v in value.values():",
    "            _scan(v, found, depth + 1)",
    "        return",
    "    if isinstance(value, (list, tuple)):",
    "        for v in value:",
    "            _scan(v, found, depth + 1)",
    "        return",
    "    cid = getattr(value, 'component_id', None)",
    "    if isinstance(cid, str):",
    "        _scan(cid, found, depth + 1)",
    "",
    "",
    "def _key(cid):",
    "    slug = cid[len('comp-'):]",
    "    base = REPO_ROOT / 'specs' / 'components' / slug",
    "    h = hashlib.sha256()",
    "    for p in sorted(base.rglob('*')):",
    "        if p.is_file():",
    "            h.update(str(p.relative_to(base)).encode('utf-8'))",
    "            h.update(b'\\0')",
    "            h.update(p.read_bytes())",
    "            h.update(b'\\0')",
    "    return 'sha256:' + h.hexdigest()",
    "",
    "",
    "def _resolve(args, kwargs):",
    "    found = []",
    "    for a in args:",
    "        _scan(a, found)",
    "    for k in sorted(kwargs):",
    "        _scan(kwargs[k], found)",
    "    if found:",
    "        return found[0]",
    "    keys = [a for a in list(args) + list(kwargs.values())",
    "            if isinstance(a, str) and a.startswith('sha256:')]",
    "    for cid in COMPONENTS:",
    "        if _key(cid) in keys:",
    "            return cid",
    "    return None",
    "",
    "",
    "def _store():",
    "    p = REPO_ROOT / '.fake-provenance' / 'store.json'",
    "    if p.is_file():",
    "        return json.loads(p.read_text(encoding='utf-8'))",
    "    return {}",
    "",
    "",
    "def _check(args, kwargs):",
    "    cid = _resolve(args, kwargs)",
    "    if cid is None:",
    "        return {'component_id': None, 'hit': False, 'key': None,",
    "                'verification_report': None, 'license_scan': None,",
    "                'secret_scan': None, 'generated_stamp': None}",
    "    key = _key(cid)",
    "    entry = _store().get(cid)",
    "    if entry and entry['key'] == key:",
    "        return {'component_id': cid, 'hit': True, 'key': key,",
    "                'verification_report': entry['verification_report'],",
    "                'license_scan': {'blocked': False, 'findings': []},",
    "                'secret_scan': {'flagged': False, 'matches': []},",
    "                'generated_stamp': entry['stamp']}",
    "    return {'component_id': cid, 'hit': False, 'key': key,",
    "            'verification_report': None, 'license_scan': None,",
    "            'secret_scan': None, 'generated_stamp': None}",
    "",
    "",
    "def current_provenance_key(*args, **kwargs):",
    "    _log('current_provenance_key')",
    "    cid = _resolve(args, kwargs)",
    "    return _key(cid) if cid else None",
    "",
    "",
    "def current_sealed_key(*args, **kwargs):",
    "    _log('current_sealed_key')",
    "    cid = _resolve(args, kwargs)",
    "    return _key(cid) if cid else None",
    "",
    "",
    "def check_provenance(*args, **kwargs):",
    "    _log('check_provenance')",
    "    return _check(args, kwargs)",
    "",
    "",
    "def check_sealed_provenance(*args, **kwargs):",
    "    _log('check_sealed_provenance')",
    "    return _check(args, kwargs)",
    "",
])


def write_fakes(repo_root, log_path):
    header = (
        "from pathlib import Path\n"
        "REPO_ROOT = Path(" + repr(str(repo_root)) + ")\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "COMPONENTS = " + repr(COMPONENTS) + "\n"
    )
    write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        header + FAKE_CHECKER_BODY,
    )
    write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "def scan(repo_root):\n"
        "    return {'flagged': False, 'matches': []}\n",
    )


# ------------------------------------------------------- simulated generate


def verification_report(component_id, results):
    overall = "pass" if all(v == "pass" for v in results.values()) else "fail"
    criteria = []
    for rid in sorted(results):
        crit = {"covers": rid, "result": results[rid]}
        if results[rid] == "fail":
            crit["failure_origin"] = "implementation"
        criteria.append(crit)
    return {
        "component_id": component_id,
        "overall": overall,
        "requirement_results": dict(results),
        "criteria": criteria,
    }


def generation_result(component_id):
    slug = component_id[len("comp-"):]
    return {
        "component_id": component_id,
        "files": ["gen/" + slug + "/" + slug + ".py"],
        "model_call_error": None,
    }


def simulate_generate(repo_root, component_id, results, stamp):
    """One `hotdocs generate` attempt: an attempt record always, provenance
    only when verification passed."""
    report = verification_report(component_id, results)
    key = component_key(repo_root, component_id)
    provenance_tracker.write_attempt_record(
        component_id,
        generation_result(component_id),
        report,
        key,
        repo_root,
    )
    if report["overall"] == "pass":
        store_path = repo_root / ".fake-provenance" / "store.json"
        store = json.loads(store_path.read_text(encoding="utf-8")) if store_path.is_file() else {}
        store[component_id] = {"key": key, "verification_report": report, "stamp": stamp}
        write(store_path, json.dumps(store, indent=2, sort_keys=True))


def run_main(argv):
    try:
        rc = provenance_tracker.main(argv)
    except SystemExit as exc:
        rc = exc.code
    return 0 if rc is None else rc


def reasons_naming(reasons, component_id):
    return [r for r in reasons if component_id in str(r)]


# ------------------------------------------------------------------ test


def test_cs_merge_visibility_001(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake-calls.log"
    build_corpus(repo_root)
    write_fakes(repo_root, log_path)
    assert_lint_clean(repo_root)

    # Step 1: a change touching three components; two pass, one fails.
    simulate_generate(repo_root, "comp-alpha", {"R-ALPHA-001": "pass"}, "alpha-run-1")
    simulate_generate(repo_root, "comp-beta", {"R-BETA-001": "pass"}, "beta-run-1")
    simulate_generate(
        repo_root, "comp-gamma", {"R-GAMMA-001": "pass", "R-GAMMA-002": "fail"}, "gamma-run-1"
    )
    assert_lint_clean(repo_root)
    capsys.readouterr()  # discard anything step 1 printed: never consulted again

    first = provenance_tracker.check_readiness(repo_root)
    assert field(first, "ready") is False
    first_components = field(first, "components")
    for cid in COMPONENTS:
        assert cid in first_components
    for cid in ("comp-alpha", "comp-beta"):
        result = first_components[cid]
        assert field(result, "hit") is True
        assert field(field(result, "verification_report"), "overall") == "pass"
    assert field(first_components["comp-gamma"], "hit") is False

    first_reasons = list(field(first, "not_ready_reasons"))
    assert reasons_naming(first_reasons, "comp-gamma"), first_reasons
    assert not reasons_naming(first_reasons, "comp-alpha"), first_reasons
    assert not reasons_naming(first_reasons, "comp-beta"), first_reasons
    assert provenance_tracker.last_requirement_failures("comp-gamma", repo_root) == ["R-GAMMA-002"]

    rc = run_main(["verify", "--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 1
    cli_first = json.loads(out)
    assert cli_first["ready"] is False
    assert any("comp-gamma" in r for r in cli_first["not_ready_reasons"])

    # Step 2: a spec edit to the failing component, then a second generate of it alone.
    edited = (
        repo_root / "specs" / "components" / "gamma" / "requirements" / "R-GAMMA-002.md"
    )
    write(
        edited,
        requirement_text("R-GAMMA-002", "The greeting MUST be at most twenty characters long."),
    )
    assert_lint_clean(repo_root)
    time.sleep(1.1)  # the new attempt's id sorts after the first one's
    simulate_generate(
        repo_root, "comp-gamma", {"R-GAMMA-001": "pass", "R-GAMMA-002": "pass"}, "gamma-run-2"
    )
    assert_lint_clean(repo_root)

    second = provenance_tracker.check_readiness(repo_root)
    second_components = field(second, "components")
    for cid in ("comp-alpha", "comp-beta"):
        before = first_components[cid]
        after = second_components[cid]
        assert field(after, "hit") is True
        assert field(field(after, "verification_report"), "overall") == "pass"
        # Same provenance as before: a hit on the first run's result, not regenerated.
        assert field(after, "key") == field(before, "key")
        assert field(after, "generated_stamp") == field(before, "generated_stamp")
    gamma = second_components["comp-gamma"]
    assert field(gamma, "hit") is True
    assert field(field(gamma, "verification_report"), "overall") == "pass"
    assert field(gamma, "generated_stamp") == "gamma-run-2"
    assert field(gamma, "key") != field(first_components["comp-gamma"], "key")

    assert list(field(second, "not_ready_reasons")) == []
    assert field(second, "ready") is True
    assert provenance_tracker.last_requirement_failures("comp-gamma", repo_root) == []

    rc = run_main(["verify", "--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    cli_second = json.loads(out)
    assert cli_second["ready"] is True
    assert cli_second["not_ready_reasons"] == []

    # The stand-in provenance-checker answered the queries.
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert any(c in ("check_provenance", "check_sealed_provenance") for c in calls)