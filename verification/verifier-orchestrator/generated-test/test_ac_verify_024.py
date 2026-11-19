# hotdocs-criterion: sha256:b9cebdf005dad51b3e4e29f3a29bc96a3669ae9717e4aab6496dfbcc3700505e
import hashlib
from pathlib import Path

import verifier_orchestrator


CRITERION_TEXT = "Given a widget value is 2\nWhen double_it is invoked with [2]\nThen result equals 4"
REQUIREMENT_TEXT = "**R-WIDGET-001** — `double_it(x)` MUST return `2 * x`."
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a test term.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n",
    )
    write(comp / "requirements" / "R-WIDGET-001.md", "# R-WIDGET-001\n\n" + REQUIREMENT_TEXT + "\n")
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget value is 2\n"
        "When double_it is invoked with [2]\n"
        "Then result equals 4\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\ndouble_it(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # Component's own code: empty module, the test imports nothing from it.
    write(repo_root / "gen" / "widget" / "widget.py", "")

    # spec-bundle-assembler stand-in.
    assembler_src = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-WIDGET-001") + ",\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr("# Library\n\n```\ndouble_it(x: int) -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_src)


def passing_test_content():
    digest = hashlib.sha256((CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")).hexdigest()
    return (
        "# hotdocs-criterion: sha256:" + digest + "\n"
        "\n"
        "def test_ok():\n"
        "    assert True\n"
    )


def error_result(category, message):
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": category, "message": message},
    }


def ok_result():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/widget/generated-test/test_ac_widget_001.py",
            "content": passing_test_content(),
        },
        "model_call_error": None,
    }


def make_author(log_path, responses):
    def stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        calls = len(log_path.read_text(encoding="utf-8").splitlines())
        index = min(calls - 1, len(responses) - 1)
        return responses[index]

    return stand_in


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len(log_path.read_text(encoding="utf-8").splitlines())


def find_criterion(report):
    for c in field(report, "criteria"):
        if field(c, "id") == CRITERION_ID:
            return c
    raise AssertionError("criterion " + CRITERION_ID + " not in report")


def test_transient_error_then_success_retries_once_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_author(log_path, [error_result("network", "dropped"), ok_result()])

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=stand_in)

    assert call_count(log_path) == 2
    criterion = find_criterion(report)
    assert field(criterion, "result") == "pass"


def test_persistent_network_error_called_twice_and_fails_with_test_origin(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_author(log_path, [error_result("network", "dropped")])

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=stand_in)

    assert call_count(log_path) == 2
    criterion = find_criterion(report)
    assert field(criterion, "result") == "fail"
    assert field(criterion, "failure_origin") == "test"
    detail = field(criterion, "failure_detail")
    assert field(detail, "message") == "test authoring failed: network: dropped"


def test_auth_error_not_retried_and_fails_with_test_origin(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_author(log_path, [error_result("auth", "bad key")])

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=stand_in)

    assert call_count(log_path) == 1
    criterion = find_criterion(report)
    assert field(criterion, "result") == "fail"
    assert field(criterion, "failure_origin") == "test"
    detail = field(criterion, "failure_detail")
    assert field(detail, "message") == "test authoring failed: auth: bad key"