# hotdocs-criterion: sha256:bbe014ef74a84d2cd41dfdb327c7c38feda09e7bca00a62799d54ec8c46b8edf
import socket
from pathlib import Path

import pytest

import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug + " component\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n\n"
        + "# " + slug + "\n\n"
        + "A fixture component.\n"
    )


def _library_md():
    return (
        "# Library\n\n"
        "```\n"
        "add(a: int, b: int) -> int\n"
        "make_widget(name: str, size: int = 1) -> Widget\n"
        "```\n"
    )


def _data_md():
    return (
        "# `Widget`\n\n"
        "```json\n"
        '{"name": "w", "size": 1}\n'
        "```\n"
    )


def _acceptance(ac_id, req_id, gherkin_lines):
    return (
        "# " + ac_id + "\n\n"
        + "Covers: " + req_id + "\n"
        + "Kind: compiled\n\n"
        + "```gherkin\n"
        + "\n".join(gherkin_lines) + "\n"
        + "```\n"
    )


def _requirement(req_id):
    return "# " + req_id + "\n\n**" + req_id + "** — The component MUST work.\n"


def _build_component(repo_root, slug, prefix, criteria):
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug))
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    _write(base / "interface" / "library.md", _library_md())
    _write(base / "interface" / "data" / "Widget.md", _data_md())
    for i, lines in enumerate(criteria, start=1):
        num = "%03d" % i
        req_id = "R-" + prefix + "-" + num
        ac_id = "AC-" + prefix + "-" + num
        _write(base / "requirements" / (req_id + ".md"), _requirement(req_id))
        _write(base / "acceptance" / (ac_id + ".md"), _acceptance(ac_id, req_id, lines))


@pytest.fixture
def no_network(monkeypatch):
    attempts = []

    def blocked(name):
        def _blocked(*args, **kwargs):
            attempts.append(name)
            raise OSError("network disabled in sandbox: " + name)
        return _blocked

    monkeypatch.setattr(socket.socket, "connect", blocked("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocked("socket.connect_ex"))
    monkeypatch.setattr(socket.socket, "sendto", blocked("socket.sendto"))
    monkeypatch.setattr(socket, "create_connection", blocked("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocked("socket.getaddrinfo"))
    monkeypatch.setattr(socket, "gethostbyname", blocked("socket.gethostbyname"))
    monkeypatch.setattr(socket, "gethostbyname_ex", blocked("socket.gethostbyname_ex"))
    return attempts


VALID_CRITERIA = [
    [
        "Given a x is 1",
        "When add is invoked with {\"a\": x, \"b\": 2}",
        "Then value equals 3",
    ],
    [
        "Given a Widget with name: \"w\", size: 2",
        "When make_widget is invoked with {\"name\": \"w\", \"size\": 2}",
        "Then size equals 2",
    ],
]

INVALID_CRITERIA = [
    [
        "Given a x is 1",
        "When a wizard appears",
        "Then value equals 3",
    ],
    [
        "When nonexistent_fn is invoked with {\"a\": 1}",
        "Then value equals 1",
    ],
    [
        "Given a x is 1",
        "When add is invoked with {\"a\": x + 1, \"b\": undefined_name}",
        "Then value.items[0] equals 3",
    ],
]


def _assert_report_complete(report):
    outputs = field(report, "outputs")
    assert isinstance(outputs, list)
    for out in outputs:
        assert field(out, "status") in ("compiled", "error")
    assert field(report, "gate_version") == "criterion-compiler@1.0.0"
    return outputs


def test_compile_makes_no_outbound_network_calls(tmp_path, no_network):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_component(repo_root, "widget", "WIDGET", VALID_CRITERIA)
    _build_component(repo_root, "broken", "BROKEN", INVALID_CRITERIA)

    valid_report = criterion_compiler.compile(
        "comp-widget", repo_root, target="pytest", out_dir=tmp_path / "out-widget"
    )
    _assert_report_complete(valid_report)

    invalid_report = criterion_compiler.compile(
        "comp-broken", repo_root, target="pytest", out_dir=tmp_path / "out-broken"
    )
    invalid_outputs = _assert_report_complete(invalid_report)
    assert any(field(o, "status") == "error" for o in invalid_outputs)

    assert no_network == [], "outbound network calls attempted: " + repr(no_network)


def test_compile_criterion_makes_no_outbound_network_calls(no_network):
    surface = criterion_compiler.InterfaceSurface(
        functions={"add": ["a", "b"]},
        types={"Widget": ["name", "size"]},
        module_name="widget",
    )
    results = []
    for i, lines in enumerate(VALID_CRITERIA + INVALID_CRITERIA, start=1):
        criterion = criterion_compiler.ParsedCriterion(
            criterion_id="AC-WIDGET-%03d" % i,
            covers="R-WIDGET-%03d" % i,
            kind="compiled",
            gherkin="\n".join(lines),
            file="specs/components/widget/acceptance/AC-WIDGET-%03d.md" % i,
        )
        results.append(criterion_compiler.compile_criterion(criterion, surface))
        results.append(criterion_compiler.compile_criterion(criterion))

    for res in results:
        assert field(res, "status") in ("compiled", "error")
    assert any(field(r, "status") == "error" for r in results)

    assert no_network == [], "outbound network calls attempted: " + repr(no_network)