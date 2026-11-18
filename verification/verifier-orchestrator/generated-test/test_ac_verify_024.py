# hotdocs-criterion: sha256:b9cebdf005dad51b3e4e29f3a29bc96a3669ae9717e4aab6496dfbcc3700505e
import hashlib
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

CRITERION_TEXT = (
    "Given a widget input of 2\n"
    "When widget_double is called with it\n"
    "Then it returns 4"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** — `widget_double(x)` MUST return `2 * x`."
INTERFACE_TEXT = "# Library\n\n```\nwidget_double(x: int) -> int\n```"
GLOSSARY_TEXT = "# Glossary\n\n- **Widget** — a test term."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT + "\n")

    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget Capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget Capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n",
    )

    comp = repo_root / "specs" / "components" / SLUG
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
        "Widget doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial.\n",
    )
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n" + CRITERION_TEXT + "\n```\n",
    )
    write(comp / "interface" / "library.md", INTERFACE_TEXT + "\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's own (empty) module.
    write(repo_root / "gen" / SLUG / "widget.py", "")

    # Fake spec-bundle-assembler, flat-module shape.
    assembler_src = (
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "INTERFACE_TEXT = " + repr(INTERFACE_TEXT) + "\n"
        "GLOSSARY_TEXT = " + repr(GLOSSARY_TEXT) + "\n"
        "\n"
        "\n"
        "class _Bundle(dict):\n"
        "    def __getattr__(self, name):\n"
        "        try:\n"
        "            return self[name]\n"
        "        except KeyError:\n"
        "            raise AttributeError(name)\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return _Bundle(\n"
        "        component_id=component_id,\n"
        "        criterion_id=criterion_id,\n"
        "        covers=" + repr(REQUIREMENT_ID) + ",\n"
        "        criterion_text=CRITERION_TEXT,\n"
        "        requirement_text=REQUIREMENT_TEXT,\n"
        "        interface=INTERFACE_TEXT,\n"
        "        glossary=GLOSSARY_TEXT,\n"
        "        dependency_interfaces={},\n"
        "    )\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )

    cached = (
        repo_root
        / "verification"
        / SLUG
        / "generated-test"
        / "test_ac_widget_001.py"
    )
    assert not cached.exists()


def correct_header():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def passing_test_content():
    return (
        correct_header() + "\n"
        "\n"
        "\n"
        "def test_ok():\n"
        "    assert 2 * 2 == 4\n"
    )


def authoring_result(model_call_error, content):
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None
        if content is None
        else {
            "path": "verification/widget/generated-test/test_ac_widget_001.py",
            "content": content,
        },
        "model_call_error": model_call_error,
    }


def make_stand_in(log_path, responses):
    """responses: list of (model_call_error, content); the last repeats."""

    def stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        calls = len(log_path.read_text(encoding="utf-8").splitlines())
        index = min(calls - 1, len(responses) - 1)
        error, content = responses[index]
        return authoring_result(error, content)

    return stand_in


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len(log_path.read_text(encoding="utf-8").splitlines())


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def test_retryable_network_error_then_success_passes(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_stand_in(
        log_path,
        [
            ({"category": "network", "message": "dropped"}, None),
            (None, passing_test_content()),
        ],
    )

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=stand_in
    )

    assert call_count(log_path) == 2
    criterion = find_criterion(report)
    assert field(criterion, "result") == "pass", criterion


def test_network_error_twice_fails_with_test_origin(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_stand_in(
        log_path,
        [({"category": "network", "message": "dropped"}, None)],
    )

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=stand_in
    )

    assert call_count(log_path) == 2
    criterion = find_criterion(report)
    assert field(criterion, "result") == "fail", criterion
    assert field(criterion, "failure_origin") == "test", criterion
    detail = field(criterion, "failure_detail")
    assert field(detail, "message") == "test authoring failed: network: dropped"


def test_auth_error_not_retried_fails_with_test_origin(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_stand_in(
        log_path,
        [({"category": "auth", "message": "bad key"}, None)],
    )

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=stand_in
    )

    assert call_count(log_path) == 1
    criterion = find_criterion(report)
    assert field(criterion, "result") == "fail", criterion
    assert field(criterion, "failure_origin") == "test", criterion
    detail = field(criterion, "failure_detail")
    assert field(detail, "message") == "test authoring failed: auth: bad key"