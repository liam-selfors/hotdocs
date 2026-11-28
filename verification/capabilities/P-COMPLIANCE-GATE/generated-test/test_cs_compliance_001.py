# hotdocs-criterion: sha256:073b1f54386aff9ed29529a3a00539d20ea622614703c41bee545e37f1a138de
import hashlib
import json
import re
from pathlib import Path

import component_gate_runner
import license_scanner
import provenance_writer
import review_packet_builder
import secret_scanner


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODEL = "anthropic:claude-sonnet-5"

LICENSED_CODE = (
    "def quantum_ledger_reconcile(alpha_entries, beta_entries, tolerance_window):\n"
    "    merged_totals = dict()\n"
    "    for entry_key, entry_amount in alpha_entries.items():\n"
    "        merged_totals[entry_key] = merged_totals.get(entry_key, 0) + entry_amount\n"
    "    for entry_key, entry_amount in beta_entries.items():\n"
    "        merged_totals[entry_key] = merged_totals.get(entry_key, 0) - entry_amount\n"
    "    return [entry_key for entry_key, balance in merged_totals.items()\n"
    "            if abs(balance) > tolerance_window]\n"
)

CLEAN_CODE = (
    "def add_numbers(first, second):\n"
    "    return first + second\n"
    "\n"
    "\n"
    "def multiply_numbers(left, right):\n"
    "    return left * right\n"
)

DRAFT_CODE = "def draft_version(value):\n    return value\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


LOG_HELPER = (
    "def _log(line):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
)


def provenance_checker_source(log_path, scenario_path):
    return (
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "SCENARIO = " + repr(str(scenario_path)) + "\n"
        + LOG_HELPER +
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key ' + component_id)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    scenario = Path(SCENARIO).read_text(encoding='utf-8').strip()\n"
        "    _log('current_provenance_key ' + component_id)\n"
        "    digit = '1' if scenario == 'licensed' else '2'\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + digit * 64,\n"
        "        'gate_versions': {'license_scanner': 'license_scanner@4.0.1',\n"
        "                          'secret_scanner': 'secret_scanner@3.1.0'},\n"
        "        'spec_bundle_parts': {'spec': 'sha256:' + 'a' * 64,\n"
        "                              'dependency_code': 'sha256:' + 'b' * 64},\n"
        "    }\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance ' + component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'manifest': None}\n"
    )


def spec_bundle_assembler_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        + LOG_HELPER +
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    _log('assemble ' + component_id + ' ' + str(mode))\n"
        "    return {'component_id': component_id, 'mode': mode, 'files': {},\n"
        "            'spec_bundle_hash': 'sha256:' + '1' * 64}\n"
    )


def generation_loop_source(log_path, scenario_path):
    return (
        "import inspect\n"
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "SCENARIO = " + repr(str(scenario_path)) + "\n"
        "LICENSED_CODE = " + repr(LICENSED_CODE) + "\n"
        "CLEAN_CODE = " + repr(CLEAN_CODE) + "\n"
        "DRAFT_CODE = " + repr(DRAFT_CODE) + "\n"
        + LOG_HELPER +
        "def make_closures(model, seed, repo_root, llm_backend):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': 'stand-in'}\n"
        "    return test_author, judge\n"
        "\n"
        "def _report(component_id, overall, run_id):\n"
        "    result = 'pass' if overall == 'pass' else 'fail'\n"
        "    return {'component_id': component_id, 'overall': overall, 'run_id': run_id,\n"
        "            'criteria': [{'criterion_id': 'AC-WIDGET-001', 'kind': 'generated-test',\n"
        "                          'covers': ['R-WIDGET-001'], 'result': result}],\n"
        "            'mutation_score': 1.0, 'assets': [], 'drivers': [], 'screenshots': []}\n"
        "\n"
        "def _generation(component_id, model, mode, retry_feedback, code, bundle):\n"
        "    if isinstance(bundle, dict):\n"
        "        bundle_hash = bundle.get('spec_bundle_hash')\n"
        "    else:\n"
        "        bundle_hash = getattr(bundle, 'spec_bundle_hash', None)\n"
        "    return {'component_id': component_id, 'files': {'gen/widget/widget.py': code},\n"
        "            'spec_bundle_hash': bundle_hash, 'model': model, 'prompt_version': 'v1',\n"
        "            'retry_feedback': retry_feedback, 'mode': mode,\n"
        "            'generator_version': 'generator@3.0.0+v11', 'transcript_sha256': None,\n"
        "            'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
        "            'model_call_error': None, 'refused': False}\n"
        "\n"
        "def _notify(on_attempt, entry, generation_result, verification_report):\n"
        "    if on_attempt is None:\n"
        "        return\n"
        "    try:\n"
        "        params = inspect.signature(on_attempt).parameters\n"
        "    except (TypeError, ValueError):\n"
        "        params = {}\n"
        "    kinds = (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)\n"
        "    named = [n for n, p in params.items() if p.kind in kinds]\n"
        "    if 'generation_result' in named and 'verification_report' in named:\n"
        "        kwargs = {}\n"
        "        for n in named:\n"
        "            if n == 'generation_result':\n"
        "                kwargs[n] = generation_result\n"
        "            elif n == 'verification_report':\n"
        "                kwargs[n] = verification_report\n"
        "            elif params[n].default is inspect.Parameter.empty:\n"
        "                kwargs[n] = entry['number'] if 'number' in n else entry\n"
        "        on_attempt(**kwargs)\n"
        "    else:\n"
        "        on_attempt(generation_result, verification_report)\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    scenario = Path(SCENARIO).read_text(encoding='utf-8').strip()\n"
        "    _log('run_attempts ' + component_id + ' ' + scenario)\n"
        "    target = Path(repo_root) / 'gen' / 'widget' / 'widget.py'\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    if scenario == 'licensed':\n"
        "        plan = [('verification_failed', DRAFT_CODE, 'fail'), ('passed', LICENSED_CODE, 'pass')]\n"
        "    else:\n"
        "        plan = [('passed', CLEAN_CODE, 'pass')]\n"
        "    attempts = []\n"
        "    feedback = sorted(retry_feedback or [])\n"
        "    gr = None\n"
        "    vr = None\n"
        "    for index, (outcome, code, overall) in enumerate(plan, start=1):\n"
        "        target.write_text(code, encoding='utf-8')\n"
        "        gr = _generation(component_id, model, mode, list(feedback), code, bundle)\n"
        "        vr = _report(component_id, overall, scenario + '-run-' + str(index))\n"
        "        entry = {'number': index, 'outcome': outcome, 'retry_feedback': list(feedback),\n"
        "                 'error_category': None,\n"
        "                 'failed_requirements': ['R-WIDGET-001'] if overall == 'fail' else [],\n"
        "                 'transcript_sha256': None}\n"
        "        attempts.append(entry)\n"
        "        _notify(on_attempt, entry, gr, vr)\n"
        "        if overall == 'fail':\n"
        "            feedback = sorted(set(feedback) | set(['R-WIDGET-001']))\n"
        "    return {'passed': True, 'stop_reason': 'passed', 'generation_result': gr,\n"
        "            'verification_report': vr,\n"
        "            'surface_report': {'ok': True, 'missing': [], 'extra': []},\n"
        "            'attempts': attempts}\n"
    )


def provenance_tracker_source(log_path, repo_root):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPO = " + repr(str(repo_root)) + "\n"
        + LOG_HELPER +
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    directory = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
        "    directory.mkdir(parents=True, exist_ok=True)\n"
        "    number = len(list(directory.iterdir())) + 1\n"
        "    if isinstance(verification_report, dict):\n"
        "        overall = verification_report.get('overall')\n"
        "    else:\n"
        "        overall = getattr(verification_report, 'overall', None)\n"
        "    record = {'component_id': component_id, 'number': number,\n"
        "              'spec_bundle_hash': spec_bundle_hash, 'overall': overall}\n"
        "    (directory / ('attempt-' + str(number) + '.json')).write_text(json.dumps(record), encoding='utf-8')\n"
        "    _log('write_attempt_record ' + component_id + ' ' + str(overall))\n"
        "\n"
        "def check_readiness(*args, **kwargs):\n"
        "    manifest_path = Path(REPO) / 'gen' / 'widget' / '.provenance.json'\n"
        "    manifest = {}\n"
        "    if manifest_path.is_file():\n"
        "        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))\n"
        "    license_scan = manifest.get('license_scan')\n"
        "    blocked = bool(license_scan.get('blocked')) if isinstance(license_scan, dict) else False\n"
        "    _log('check_readiness blocked=' + str(blocked))\n"
        "    entry = {'component_id': 'comp-widget', 'ready': not blocked,\n"
        "             'status': 'blocked' if blocked else 'ready', 'reasons': [],\n"
        "             'verification_report': manifest.get('verification_report'),\n"
        "             'license_scan': license_scan,\n"
        "             'secret_scan': manifest.get('secret_scan'),\n"
        "             'provenance_hit': manifest.get('provenance_hit', False)}\n"
        "    return {'ready': not blocked, 'overall': 'fail' if blocked else 'pass',\n"
        "            'components': {'comp-widget': entry}, 'capabilities': {}}\n"
    )


def cache_manager_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        + LOG_HELPER +
        "class CacheKey:\n"
        "    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None, gate_version=None, model_pin=None):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_inputs_hash = gate_inputs_hash\n"
        "        self.gate_version = gate_version\n"
        "        self.model_pin = model_pin\n"
        "\n"
        "class CachedResult:\n"
        "    def __init__(self, gate_type=None, payload=None, stored_at=None):\n"
        "        self.gate_type = gate_type\n"
        "        self.payload = payload\n"
        "        self.stored_at = stored_at\n"
        "\n"
        "class Miss:\n"
        "    def __init__(self, reason):\n"
        "        self.reason = reason\n"
        "        self.payload = None\n"
        "\n"
        "def get(cache_key, repo_root=None):\n"
        "    _log('cache_get')\n"
        "    return Miss('stand-in never hits')\n"
        "\n"
        "def put(cache_key, cached_result, repo_root=None):\n"
        "    _log('cache_put')\n"
    )


def build_spec_fixture(repo_root):
    base = repo_root / "specs" / "components" / SLUG
    write(base / "component.md",
          "---\n"
          "id: comp-widget\n"
          "title: Widget\n"
          "status: draft\n"
          "owners: [pipeline-team]\n"
          "sealed: true\n"
          "source_path: legacy/widget/\n"
          "depends_on: []\n"
          "---\n"
          "\n"
          "# Widget\n"
          "\n"
          "A small fixture component.\n")
    write(base / "requirements" / "R-WIDGET-001.md",
          "# R-WIDGET-001\n\nThe widget reconciles two ledgers.\n")
    write(base / "acceptance" / "AC-WIDGET-001.md",
          "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\n\nGiven two ledgers, when reconciled, then imbalances are listed.\n")
    write(base / "constraints.md", "# Constraints\n\nNone.\n")


def read_log(log_path):
    if not log_path.is_file():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def widget_flags(packet):
    flags = field(packet, "compliance_flags")
    entries = field(flags, "license_scan")
    return [e for e in entries if field(e, "component_id") == COMPONENT_ID]


def test_cs_compliance_001_license_flag_blocks_records_and_surfaces(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    control = tmp_path / "control"
    control.mkdir()
    log_path = control / "calls.log"
    scenario_path = control / "scenario.txt"

    corpus_path = control / "corpus.json"
    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.5,
        "entries": [
            {"reference_id": "ref-ledger", "license_family": "GPL", "risk_tier": "medium",
             "hashes": window_hashes(LICENSED_CODE)},
        ],
    }
    assert corpus["entries"][0]["hashes"]
    assert not set(window_hashes(CLEAN_CODE)) & set(corpus["entries"][0]["hashes"])
    write(corpus_path, json.dumps(corpus))

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    build_spec_fixture(repo_root)
    gen = repo_root / "gen"
    write(gen / "provenance-checker" / "provenance_checker.py",
          provenance_checker_source(log_path, scenario_path))
    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
          spec_bundle_assembler_source(log_path))
    write(gen / "generation-loop" / "generation_loop.py",
          generation_loop_source(log_path, scenario_path))
    write(gen / "provenance-tracker" / "provenance_tracker.py",
          provenance_tracker_source(log_path, repo_root))
    write(gen / "cache-manager" / "cache_manager.py",
          cache_manager_source(log_path))

    manifest_path = repo_root / "gen" / SLUG / ".provenance.json"

    # ---- Run 1: a retried generation whose final candidate matches licensed code ----
    write(scenario_path, "licensed\n")
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    log = read_log(log_path)
    assert any(line.startswith("run_attempts " + COMPONENT_ID + " licensed") for line in log)
    attempt_records = [line for line in log if line.startswith("write_attempt_record")]
    assert len(attempt_records) == 2
    assert attempt_records[0].endswith(" fail")

    attempts = field(result, "attempts")
    assert len(attempts) == 2
    assert field(attempts[0], "outcome") == "verification_failed"

    scan1 = field(result, "license_scan")
    assert field(scan1, "evaluated") is True
    assert field(scan1, "blocked") is True
    assert field(scan1, "similarity_score") >= field(scan1, "block_threshold")

    assert manifest_path.is_file()
    manifest1 = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded1 = manifest1["license_scan"]
    assert recorded1["blocked"] is True
    assert recorded1["evaluated"] is True
    assert recorded1["similarity_score"] == field(scan1, "similarity_score")
    assert recorded1["gate_version"] == field(scan1, "gate_version")

    readiness_before = len([l for l in read_log(log_path) if l.startswith("check_readiness")])
    packet1 = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    readiness_calls = [l for l in read_log(log_path) if l.startswith("check_readiness")]
    assert len(readiness_calls) > readiness_before
    assert readiness_calls[-1] == "check_readiness blocked=True"

    flags1 = widget_flags(packet1)
    assert flags1, "the license finding must appear in the review packet"
    blocked_entries = [e for e in flags1 if field(field(e, "result"), "blocked") is True]
    assert blocked_entries
    assert field(field(blocked_entries[0], "result"), "similarity_score") == recorded1["similarity_score"]

    # ---- Run 2: a later, separate run whose scan is clean ----
    write(scenario_path, "clean\n")
    result2 = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    assert any(line.startswith("run_attempts " + COMPONENT_ID + " clean") for line in read_log(log_path))
    scan2 = field(result2, "license_scan")
    assert field(scan2, "evaluated") is True
    assert field(scan2, "blocked") is False
    assert field(scan2, "similarity_score") < field(scan2, "block_threshold")

    manifest2 = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded2 = manifest2["license_scan"]
    assert recorded2["blocked"] is False
    assert recorded2["evaluated"] is True
    assert recorded2["similarity_score"] == field(scan2, "similarity_score")
    assert recorded2["similarity_score"] != recorded1["similarity_score"]

    readiness_before = len([l for l in read_log(log_path) if l.startswith("check_readiness")])
    packet2 = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    readiness_calls = [l for l in read_log(log_path) if l.startswith("check_readiness")]
    assert len(readiness_calls) > readiness_before
    assert readiness_calls[-1] == "check_readiness blocked=False"

    for entry in widget_flags(packet2):
        entry_result = field(entry, "result")
        assert field(entry_result, "blocked") is False
        assert field(entry_result, "similarity_score") == recorded2["similarity_score"]