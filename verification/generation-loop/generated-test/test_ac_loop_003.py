# hotdocs-criterion: sha256:c17479418d98efa23c946f361bc322a7644b4419b186e95ac7359b9457a25b06
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-widget"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_generator(repo_root, log_path):
    src = (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "@dataclass\n"
        "class GenerationResult:\n"
        "    component_id: str = ''\n"
        "    spec_bundle_hash: str = ''\n"
        "    model: str = ''\n"
        "    prompt_version: str = ''\n"
        "    cache_hit: bool = False\n"
        "    files: dict = field(default_factory=dict)\n"
        "    model_call_error: object = None\n"
        "    refused: object = None\n"
        "    retry_feedback: object = None\n"
        "    mode: str = 'single'\n"
        "    transcript_sha256: object = None\n"
        "    turns: int = 1\n"
        "    tool_calls: int = 0\n"
        "    isolation: object = None\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    fb = None if retry_feedback is None else list(retry_feedback)\n"
        "    _log({'call': 'generate', 'feedback': fb,\n"
        "          'args': repr((bundle, model, retry_feedback, repo_root, llm_backend))})\n"
        "    return GenerationResult(\n"
        "        component_id=bundle['component_id'],\n"
        "        spec_bundle_hash=bundle['spec_bundle_hash'],\n"
        "        model=model,\n"
        "        prompt_version='v12',\n"
        "        cache_hit=False,\n"
        "        files={'widget.py': 'X = 1\\n'},\n"
        "        model_call_error=None,\n"
        "        refused=None,\n"
        "        retry_feedback=fb,\n"
        "    )\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log({'call': 'commit_cache', 'args': repr(repo_root)})\n"
        "\n"
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    return None\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    return None\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    return (None, [])\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    return (None, [])\n"
    )
    write(repo_root / "gen" / "generator" / "generator.py", src)


def build_surface_checker(repo_root, log_path):
    src = (
        "import json\n"
        "from dataclasses import dataclass, field, asdict\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "\n"
        "@dataclass\n"
        "class SurfaceReport:\n"
        "    ok: bool = True\n"
        "    findings: list = field(default_factory=list)\n"
        "    def to_dict(self):\n"
        "        return asdict(self)\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': 'check_surface', 'component_id': component_id}) + '\\n')\n"
        "    return SurfaceReport(ok=True, findings=[])\n"
    )
    write(repo_root / "gen" / "surface-checker" / "surface_checker.py", src)


REPORTS = [
    {
        "overall": "fail",
        "criteria": [
            {"id": "AC-W-3", "covers": "R-W-3", "kind": "generated-test", "result": "fail",
             "failure_origin": "implementation"},
            {"id": "AC-W-1", "covers": "R-W-1", "kind": "generated-test", "result": "fail",
             "failure_origin": "test"},
            {"id": "AC-W-2", "covers": "R-W-2", "kind": "generated-test", "result": "pass"},
        ],
    },
    {
        "overall": "fail",
        "criteria": [
            {"id": "AC-W-2", "covers": "R-W-2", "kind": "generated-test", "result": "fail",
             "failure_origin": "implementation",
             "failure_detail": {"message": "secret detail"}},
        ],
    },
    {
        "overall": "pass",
        "criteria": [],
    },
]


def build_verifier(repo_root, log_path, counter_path):
    src = (
        "import json\n"
        "import copy\n"
        "from dataclasses import dataclass, field, asdict\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "COUNTER_PATH = " + repr(str(counter_path)) + "\n"
        "REPORTS = " + repr(REPORTS) + "\n"
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "@dataclass\n"
        "class VerificationReport:\n"
        "    component_id: str = ''\n"
        "    criteria: list = field(default_factory=list)\n"
        "    requirement_results: dict = field(default_factory=dict)\n"
        "    interface_drift: bool = False\n"
        "    mutation_score: object = None\n"
        "    mutation_error: object = None\n"
        "    assets: list = field(default_factory=list)\n"
        "    overall: str = 'pass'\n"
        "    def to_dict(self):\n"
        "        return asdict(self)\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    try:\n"
        "        with open(COUNTER_PATH, 'r', encoding='utf-8') as fh:\n"
        "            n = int(fh.read().strip() or '0')\n"
        "    except FileNotFoundError:\n"
        "        n = 0\n"
        "    with open(COUNTER_PATH, 'w', encoding='utf-8') as fh:\n"
        "        fh.write(str(n + 1))\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': 'verify', 'n': n}) + '\\n')\n"
        "    spec = copy.deepcopy(REPORTS[min(n, len(REPORTS) - 1)])\n"
        "    rr = {}\n"
        "    for c in spec['criteria']:\n"
        "        rr[c['covers']] = c['result']\n"
        "    return VerificationReport(\n"
        "        component_id=component_id,\n"
        "        criteria=spec['criteria'],\n"
        "        requirement_results=rr,\n"
        "        interface_drift=False,\n"
        "        mutation_score=None,\n"
        "        mutation_error=None,\n"
        "        assets=[],\n"
        "        overall=spec['overall'],\n"
        "    )\n"
    )
    write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", src)


def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_loop_003_feedback_accumulates_only_failed_requirement_ids(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_log = logs / "generator.log"
    surf_log = logs / "surface.log"
    ver_log = logs / "verify.log"
    counter = logs / "verify_counter.txt"

    build_generator(repo_root, gen_log)
    build_surface_checker(repo_root, surf_log)
    build_verifier(repo_root, ver_log, counter)

    bundle = {"component_id": COMPONENT_ID, "spec_bundle_hash": "sha256:abc", "hint_code": None}

    result = generation_loop.run_attempts(
        COMPONENT_ID,
        bundle,
        repo_root,
        "mock:model",
        mode="single",
        max_attempts=3,
        retry_feedback=["R-W-9", "R-W-9"],
    )

    gen_entries = [e for e in read_log(gen_log) if e["call"] == "generate"]
    feedbacks = [e["feedback"] for e in gen_entries]
    assert feedbacks == [
        ["R-W-9"],
        ["R-W-3", "R-W-9"],
        ["R-W-2", "R-W-3", "R-W-9"],
    ]

    attempts = field(result, "attempts")
    assert len(attempts) == 3
    failed = [list(field(a, "failed_requirements")) for a in attempts]
    assert failed == [["R-W-3"], ["R-W-2"], []]

    for entry in gen_entries:
        assert "secret detail" not in entry["args"]
        assert "secret detail" not in json.dumps(entry["feedback"])
    assert "secret detail" not in gen_log.read_text(encoding="utf-8")