# hotdocs-criterion: sha256:0a4703bf8c9dec87ac16a192225a4a19ce1ab0403e991feb886333236439b389
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"
CRITERION_ID = "AC-WIDGET-001"

BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-WIDGET-001",
    "criterion_text": "Given a widget\nWhen it runs\nThen it works",
    "requirement_text": "R-WIDGET-001: the widget MUST work.",
    "interface": "# Library\n\nwidget_run(x) -> int",
    "glossary": "# Glossary\n",
    "dependency_interfaces": {},
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_line():
    payload = json.dumps(
        {k: BUNDLE[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\nA widget used as a verification fixture.\n\n"
        "## Scope\n\n- In scope: running.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST work.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nwidget_run(x) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Widget capability\n\n"
        "## Purpose\n\nWidgets.\n\n"
        "## Scope\n\n- Widgets.\n\n"
        "### CS-WIDGET-001\n\n"
        "Covers: P-WIDGET\n\n"
        "```gherkin\nGiven a widget\nWhen it runs\nThen it works\n```\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), "")

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    b = dict(BUNDLE)\n"
        "    b['component_id'] = component_id\n"
        "    b['criterion_id'] = criterion_id\n"
        "    return b\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )


def passing_test_content():
    return header_line() + "\n\n\ndef test_widget_passes():\n    assert True\n"


def make_author(log_path, responses):
    """responses: function of call number (1-based) -> (model_call_error, file)."""

    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        n = len(log_path.read_text(encoding="utf-8").splitlines())
        error, file_ = responses(n)
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": file_,
            "model_call_error": error,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len(log_path.read_text(encoding="utf-8").splitlines())


def criterion_entry(report):
    for c in field(report, "criteria"):
        if field(c, "id") == CRITERION_ID:
            return c
    raise AssertionError("criterion " + CRITERION_ID + " not in report")


def detail_message(entry):
    detail = field(entry, "failure_detail")
    return field(detail, "message")


def test_network_error_then_success_retries_once_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    def responses(n):
        if n == 1:
            return {"category": "network", "message": "dropped"}, None
        return None, {
            "path": "verification/widget/generated-test/test_ac_widget_001.py",
            "content": passing_test_content(),
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(log_path, responses)
    )

    assert call_count(log_path) == 2
    entry = criterion_entry(report)
    assert field(entry, "result") == "pass"


def test_network_error_always_fails_after_two_calls(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    def responses(n):
        return {"category": "network", "message": "dropped"}, None

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(log_path, responses)
    )

    assert call_count(log_path) == 2
    entry = criterion_entry(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    assert detail_message(entry) == "test authoring failed: network: dropped"


def test_auth_error_is_not_retried(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    def responses(n):
        return {"category": "auth", "message": "bad key"}, None

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(log_path, responses)
    )

    assert call_count(log_path) == 1
    entry = criterion_entry(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    assert detail_message(entry) == "test authoring failed: auth: bad key"