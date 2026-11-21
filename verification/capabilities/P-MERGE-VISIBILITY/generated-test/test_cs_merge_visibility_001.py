# hotdocs-criterion: sha256:196c9b80077d40baa9fc622d246a4fd965b3f884a4b07df404f2293a89813aee
import provenance_tracker
import provenance_tracker_ui

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_spec_linter():
    gen = next(p for p in Path(provenance_tracker.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


SLUGS = ["alpha", "beta", "gamma"]
PREFIX = {"alpha": "ALPHA", "beta": "BETA", "gamma": "GAMMA"}


def _write_component(repo_root, slug, purpose_text):
    base = repo_root / "specs" / "components" / slug
    (base / "requirements").mkdir(parents=True, exist_ok=True)
    (base / "acceptance").mkdir(parents=True, exist_ok=True)
    (base / "interface").mkdir(parents=True, exist_ok=True)
    pfx = PREFIX[slug]
    rid = "R-" + pfx + "-001"
    acid = "AC-" + pfx + "-001"
    (base / "component.md").write_text(
        "---\n"
        "id: comp-" + slug + "\n"
        "title: Component " + slug + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Component " + slug + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose_text + "\n"
    )
    (base / "requirements" / (rid + ".md")).write_text(
        "# " + rid + "\n"
        "\n"
        "The component MUST return its input unchanged.\n"
    )
    (base / "acceptance" / (acid + ".md")).write_text(
        "# " + acid + "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an input\n"
        "When the component is called\n"
        "Then it returns the input unchanged\n"
        "```\n"
    )
    (base / "interface" / "library.md").write_text(
        "# Library\n"
        "\n"
        "```\n"
        "identity(x) -> x\n"
        "```\n"
    )
    (base / "constraints.md").write_text("# Constraints\n\nNone.\n")


def _spec_key(repo_root, slug):
    base = repo_root / "specs" / "components" / slug
    h = hashlib.sha256()
    for p in sorted(base.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(base)).encode())
            h.update(p.read_bytes())
    return "sha256:" + h.hexdigest()


def _write_fake_checker(repo_root, log_path, store_path):
    d = repo_root / "gen" / "provenance-checker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import hashlib\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "REPO_ROOT = Path(" + repr(str(repo_root)) + ")\n"
        "LOG = Path(" + repr(str(log_path)) + ")\n"
        "STORE = Path(" + repr(str(store_path)) + ")\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def _cid(args, kwargs):\n"
        "    for v in list(args) + list(kwargs.values()):\n"
        "        if isinstance(v, str) and v.startswith('comp-'):\n"
        "            return v\n"
        "    return None\n"
        "\n"
        "def _key(cid):\n"
        "    base = REPO_ROOT / 'specs' / 'components' / cid[len('comp-'):]\n"
        "    h = hashlib.sha256()\n"
        "    for p in sorted(base.rglob('*')):\n"
        "        if p.is_file():\n"
        "            h.update(str(p.relative_to(base)).encode())\n"
        "            h.update(p.read_bytes())\n"
        "    return 'sha256:' + h.hexdigest()\n"
        "\n"
        "def current_sealed_key(*args, **kwargs):\n"
        "    _log('current_sealed_key ' + str(_cid(args, kwargs)))\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(*args, **kwargs):\n"
        "    cid = _cid(args, kwargs)\n"
        "    _log('current_provenance_key ' + str(cid))\n"
        "    return _key(cid)\n"
        "\n"
        "def _result(cid, key):\n"
        "    store = json.loads(STORE.read_text()) if STORE.is_file() else {}\n"
        "    entry = store.get(cid)\n"
        "    if entry is None or entry['key'] != key:\n"
        "        return {'component_id': cid, 'hit': False, 'provenance_key': key,\n"
        "                'manifest_path': None, 'verification_report': None,\n"
        "                'license_scan': None, 'secret_scan': None}\n"
        "    return {'component_id': cid, 'hit': True, 'provenance_key': key,\n"
        "            'manifest_path': str(REPO_ROOT / 'verification' / cid[len('comp-'):] / '.provenance.json'),\n"
        "            'verification_report': {'overall': entry['overall'],\n"
        "                                    'requirement_results': entry['requirement_results'],\n"
        "                                    'criteria': entry['criteria']},\n"
        "            'license_scan': {'blocked': False, 'findings': []},\n"
        "            'secret_scan': {'flagged': False, 'findings': []}}\n"
        "\n"
        "def check_provenance(*args, **kwargs):\n"
        "    cid = _cid(args, kwargs)\n"
        "    _log('check_provenance ' + str(cid))\n"
        "    return _result(cid, _key(cid))\n"
        "\n"
        "def check_sealed_provenance(*args, **kwargs):\n"
        "    cid = _cid(args, kwargs)\n"
        "    _log('check_sealed_provenance ' + str(cid))\n"
        "    return _result(cid, _key(cid))\n"
    )
    (d / "provenance_checker.py").write_text(src)


def _generate(repo_root, store_path, slug, passing):
    """Simulate one `hotdocs generate` attempt: record the attempt and its provenance."""
    cid = "comp-" + slug
    rid = "R-" + PREFIX[slug] + "-001"
    key = _spec_key(repo_root, slug)
    result = "pass" if passing else "fail"
    criteria = [{"criterion_id": "AC-" + PREFIX[slug] + "-001", "covers": rid, "result": result}]
    if not passing:
        criteria[0]["failure_origin"] = "implementation"
    verification = {
        "component_id": cid,
        "overall": result,
        "requirement_results": {rid: result},
        "criteria": criteria,
    }
    generation = {
        "component_id": cid,
        "model": "anthropic:claude-opus-5-5",
        "files": {},
        "model_call_error": None,
    }
    provenance_tracker.write_attempt_record(cid, generation, verification, key, repo_root)
    store = json.loads(store_path.read_text()) if store_path.is_file() else {}
    store[cid] = {
        "key": key,
        "overall": result,
        "requirement_results": {rid: result},
        "criteria": criteria,
    }
    store_path.write_text(json.dumps(store))
    return key


def _attempt_count(repo_root, cid):
    d = repo_root / ".hotdocs" / "attempts" / cid
    return len(list(d.glob("*.json"))) if d.is_dir() else 0


def test_cs_merge_visibility_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "specs").mkdir()
    (repo_root / "specs" / "glossary.md").write_text("# Glossary\n\n- **Widget** — a thing.\n")
    for slug in SLUGS:
        _write_component(repo_root, slug, "Returns its input unchanged.")

    log_path = tmp_path / "checker.log"
    store_path = repo_root / ".fake-provenance.json"
    _write_fake_checker(repo_root, log_path, store_path)

    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # Step 1: a change touching three components; two generate and verify, one fails.
    key_a1 = _generate(repo_root, store_path, "alpha", True)
    key_b1 = _generate(repo_root, store_path, "beta", True)
    key_c1 = _generate(repo_root, store_path, "gamma", False)

    report1 = provenance_tracker.check_readiness(repo_root)
    assert log_path.is_file() and "check_provenance" in log_path.read_text()

    assert field(report1, "ready") is False
    comps1 = field(report1, "components")
    for cid in ("comp-alpha", "comp-beta", "comp-gamma"):
        assert cid in comps1
    assert field(comps1["comp-alpha"], "hit") is True
    assert field(field(comps1["comp-alpha"], "verification_report"), "overall") == "pass"
    assert field(comps1["comp-beta"], "hit") is True
    assert field(field(comps1["comp-beta"], "verification_report"), "overall") == "pass"
    assert field(field(comps1["comp-gamma"], "verification_report"), "overall") == "fail"

    reasons1 = list(field(report1, "not_ready_reasons"))
    assert any("comp-gamma" in r for r in reasons1)
    assert not any("comp-alpha" in r for r in reasons1)
    assert not any("comp-beta" in r for r in reasons1)
    # The reason is recoverable without the first run's CLI output.
    assert provenance_tracker.last_requirement_failures("comp-gamma", repo_root) == ["R-GAMMA-001"]

    # Step 2: spec edit to the failing component, then regenerate only it.
    _write_component(repo_root, "gamma", "Returns its input unchanged, now clarified.")
    assert spec_linter.lint(None, repo_root).hard_failures == 0
    key_c2 = _generate(repo_root, store_path, "gamma", True)
    assert key_c2 != key_c1
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report2 = provenance_tracker.check_readiness(repo_root)
    assert field(report2, "ready") is True
    assert list(field(report2, "not_ready_reasons")) == []
    comps2 = field(report2, "components")

    for cid, key in (("comp-alpha", key_a1), ("comp-beta", key_b1)):
        r = comps2[cid]
        assert field(r, "hit") is True
        assert field(r, "provenance_key") == key
        assert field(field(r, "verification_report"), "overall") == "pass"
        # Not regenerated: still exactly one attempt.
        assert _attempt_count(repo_root, cid) == 1

    rc = comps2["comp-gamma"]
    assert field(rc, "hit") is True
    assert field(rc, "provenance_key") == key_c2
    assert field(field(rc, "verification_report"), "overall") == "pass"
    assert _attempt_count(repo_root, "comp-gamma") == 2