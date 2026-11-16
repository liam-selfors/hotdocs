"""AC-COMPILE-008 (covers R-COMPILE-008).

Given any component's acceptance/ and interface/ content, valid or invalid,
when compile-criteria runs under a network-disabled sandbox, compilation
completes (successfully or with a compile error) with no outbound network
calls of any kind.
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

import criterion_compiler


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_MODEL_OR_NET_EXECUTABLES = {
    "claude",
    "ollama",
    "curl",
    "wget",
    "ssh",
    "nc",
    "ncat",
    "telnet",
    "ftp",
}


class _NetworkAttempt(OSError):
    pass


@pytest.fixture
def network_sandbox(monkeypatch, tmp_path):
    """Disable all network access, recording every attempt.

    Every attempt is both recorded (so the test can assert on it even if the
    component swallows the resulting exception) and refused with an OSError.
    """
    attempts = []

    def _record(kind, detail):
        attempts.append((kind, repr(detail)))
        raise _NetworkAttempt("network disabled in sandbox: %s %r" % (kind, detail))

    def fake_connect(self, address, *a, **k):
        _record("socket.connect", address)

    def fake_connect_ex(self, address, *a, **k):
        _record("socket.connect_ex", address)

    def fake_sendto(self, *a, **k):
        _record("socket.sendto", a)

    def fake_sendmsg(self, *a, **k):
        _record("socket.sendmsg", a)

    def fake_create_connection(address, *a, **k):
        _record("socket.create_connection", address)

    def fake_getaddrinfo(host, *a, **k):
        _record("socket.getaddrinfo", host)

    def fake_gethostbyname(host, *a, **k):
        _record("socket.gethostbyname", host)

    def fake_gethostbyname_ex(host, *a, **k):
        _record("socket.gethostbyname_ex", host)

    monkeypatch.setattr(socket.socket, "connect", fake_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", fake_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", fake_sendto)
    if hasattr(socket.socket, "sendmsg"):
        monkeypatch.setattr(socket.socket, "sendmsg", fake_sendmsg)
    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", fake_gethostbyname)
    monkeypatch.setattr(socket, "gethostbyname_ex", fake_gethostbyname_ex)

    # A model invoked through an external CLI (e.g. `claude`, `ollama`) or a
    # network tool would make its outbound calls from a child process; record
    # and refuse those launches too.
    original_popen_init = subprocess.Popen.__init__

    def fake_popen_init(self, args, *a, **k):
        if isinstance(args, (str, bytes, os.PathLike)):
            text = os.fsdecode(args) if not isinstance(args, str) else args
            first = text.strip().split()[0] if text.strip() else ""
        else:
            seq = list(args)
            first = os.fsdecode(seq[0]) if seq else ""
        base = os.path.basename(first)
        if base in _MODEL_OR_NET_EXECUTABLES:
            _record("subprocess", args)
        return original_popen_init(self, args, *a, **k)

    monkeypatch.setattr(subprocess.Popen, "__init__", fake_popen_init)

    # Make any accidental model client believe credentials exist so that an
    # attempted call would actually reach the (blocked) network layer rather
    # than bail out early and hide the attempt.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-sandbox-not-a-real-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-sandbox-not-a-real-key")
    for proxy_var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(proxy_var, raising=False)

    return attempts


# ---------------------------------------------------------------------------
# synthetic corpus fixtures
# ---------------------------------------------------------------------------


def _component_md(slug: str) -> str:
    return (
        "---\n"
        "id: comp-%s\n"
        "title: %s\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/%s\n"
        "---\n"
        "\n"
        "# %s\n"
        "\n"
        "Synthetic component for AC-COMPILE-008.\n"
    ) % (slug, slug, slug, slug)


def _acceptance(criterion_id: str, covers: str, kind: str, gherkin: str) -> str:
    return (
        "# %s\n"
        "\n"
        "Covers: %s\n"
        "Kind: %s\n"
        "\n"
        "```gherkin\n"
        "%s"
        "```\n"
    ) % (criterion_id, covers, kind, gherkin)


def _build_valid_component(repo_root: Path) -> str:
    slug = "widget-maker"
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug))
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    for n in ("001", "002", "003", "004"):
        _write(
            base / "requirements" / ("R-WID-%s.md" % n),
            "# R-WID-%s\n\n**R-WID-%s** — The widget maker MUST make widgets.\n" % (n, n),
        )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n"
        "```\n"
        "make_widget(name: str, size: int = 1) -> Widget\n"
        "count_widgets(items: list) -> int\n"
        "```\n",
    )
    _write(
        base / "interface" / "data" / "Widget.md",
        "# `Widget`\n\n"
        "```json\n"
        '{"name": "w1", "size": 3}\n'
        "```\n",
    )
    # valid compiled criterion
    _write(
        base / "acceptance" / "AC-WID-001.md",
        _acceptance(
            "AC-WID-001",
            "R-WID-001",
            "compiled",
            'Given a name is "w1"\n'
            'When make_widget is invoked with {"name": name, "size": 3}\n'
            "Then size equals 3\n",
        ),
    )
    # invalid: unmatched step
    _write(
        base / "acceptance" / "AC-WID-002.md",
        _acceptance(
            "AC-WID-002",
            "R-WID-002",
            "compiled",
            'Given a name is "w1"\n'
            "When a wizard appears\n"
            "Then size equals 3\n",
        ),
    )
    # invalid: function not in interface + expression literal
    _write(
        base / "acceptance" / "AC-WID-003.md",
        _acceptance(
            "AC-WID-003",
            "R-WID-003",
            "compiled",
            "Given a count is 2\n"
            "When summon_dragon is invoked with [count + 1]\n"
            "Then result equals null\n",
        ),
    )
    # non-compiled kind (skipped by the compiler)
    _write(
        base / "acceptance" / "AC-WID-004.md",
        _acceptance(
            "AC-WID-004",
            "R-WID-004",
            "generated-test",
            "Given any widget\n"
            "When it is made\n"
            "Then it is a widget\n",
        ),
    )
    return slug


def _build_broken_component(repo_root: Path) -> str:
    slug = "broken-thing"
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug))
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        base / "requirements" / "R-BRK-001.md",
        "# R-BRK-001\n\n**R-BRK-001** — The broken thing MUST exist.\n",
    )
    _write(
        base / "requirements" / "R-BRK-002.md",
        "# R-BRK-002\n\n**R-BRK-002** — The broken thing MUST be broken.\n",
    )
    # malformed interface: unterminated fence, junk lines
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\n((( not a signature\ndef nope(:\n",
    )
    # malformed data type: JSON example that does not parse
    _write(
        base / "interface" / "data" / "Gadget.md",
        "# `Gadget`\n\n```json\n{this is not json,,,\n```\n",
    )
    # acceptance with no gherkin fence at all
    _write(
        base / "acceptance" / "AC-BRK-001.md",
        "# AC-BRK-001\n\nCovers: R-BRK-001\nKind: compiled\n\nNo steps here.\n",
    )
    # acceptance referencing an unbound identifier and a missing type
    _write(
        base / "acceptance" / "AC-BRK-002.md",
        _acceptance(
            "AC-BRK-002",
            "R-BRK-002",
            "compiled",
            'Given a Gadget with name: "g", owner: nobody\n'
            "When nothing_here is invoked with {\"x\": ghost.field}\n"
            "Then result[0].x equals {\"a\": [1, true, null]}\n",
        ),
    )
    return slug


def _run_compile_any_id(slug: str, repo_root: Path, out_dir: Path):
    """Call compile() with the comp- id, falling back to the bare slug.

    Every call happens inside the network sandbox; whichever id form the
    implementation accepts, neither may touch the network.
    """
    reports = []
    for cid in ("comp-" + slug, slug):
        try:
            report = criterion_compiler.compile(cid, repo_root, "pytest", out_dir)
        except _NetworkAttempt:
            raise
        except (SystemExit, KeyError, ValueError, FileNotFoundError, LookupError):
            # an unknown-id usage-style failure is a legitimate "completion"
            # for one id form; try the other form.
            continue
        reports.append(report)
        outputs = _get(report, "outputs") or []
        if len(list(outputs)) > 0:
            break
    return reports


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_compile_library_makes_no_network_calls(network_sandbox, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    valid_slug = _build_valid_component(repo_root)
    broken_slug = _build_broken_component(repo_root)

    reports = []
    reports += _run_compile_any_id(valid_slug, repo_root, tmp_path / "out_valid")
    reports += _run_compile_any_id(broken_slug, repo_root, tmp_path / "out_broken")

    assert network_sandbox == [], (
        "compile() attempted outbound network access: %r" % (network_sandbox,)
    )

    # Compilation completed and produced reports for at least one component.
    assert reports, "compile() never completed with a report for either component"
    for report in reports:
        assert _get(report, "gate_version") == "criterion-compiler@1.0.0"
        outputs = list(_get(report, "outputs") or [])
        for entry in outputs:
            assert _get(entry, "status") in ("compiled", "error")


def test_compile_reports_both_success_and_error_without_network(network_sandbox, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    valid_slug = _build_valid_component(repo_root)

    reports = _run_compile_any_id(valid_slug, repo_root, tmp_path / "out")

    assert network_sandbox == [], (
        "compile() attempted outbound network access: %r" % (network_sandbox,)
    )

    populated = [r for r in reports if list(_get(r, "outputs") or [])]
    assert populated, "compile() produced no outputs for a component with criteria"
    statuses = {
        _get(entry, "criterion_id"): _get(entry, "status")
        for entry in list(_get(populated[-1], "outputs") or [])
    }
    # Invalid criteria completed as compile errors, not as crashes.
    assert statuses.get("AC-WID-002") == "error"
    assert statuses.get("AC-WID-003") == "error"


def test_compile_criterion_makes_no_network_calls(network_sandbox, tmp_path):
    PC = criterion_compiler.ParsedCriterion
    IS = criterion_compiler.InterfaceSurface

    surface = IS(
        functions={"make_widget": ["name", "size"]},
        types={"Widget": ["name", "size"]},
        module_name="widget_maker",
    )

    cases = [
        # valid, no surface
        (
            PC(
                criterion_id="AC-X-001",
                covers="R-X-001",
                kind="compiled",
                gherkin='Given a payload is {"a": 1}\nThen payload equals {"a": 1}\n',
                file="x/AC-X-001.md",
            ),
            None,
        ),
        # valid, with surface
        (
            PC(
                criterion_id="AC-X-002",
                covers="R-X-002",
                kind="compiled",
                gherkin=(
                    'Given a Widget with name: "w", size: 2\n'
                    'When make_widget is invoked with {"name": "w", "size": 2}\n'
                    "Then size equals 2\n"
                ),
                file="x/AC-X-002.md",
            ),
            surface,
        ),
        # invalid: unmatched step
        (
            PC(
                criterion_id="AC-X-003",
                covers="R-X-003",
                kind="compiled",
                gherkin="When a wizard appears\n",
                file="x/AC-X-003.md",
            ),
            surface,
        ),
        # invalid: function call without a surface
        (
            PC(
                criterion_id="AC-X-004",
                covers="R-X-004",
                kind="compiled",
                gherkin='When make_widget is invoked with {"name": "w"}\n',
                file="x/AC-X-004.md",
            ),
            None,
        ),
        # invalid: expression and unresolved reference
        (
            PC(
                criterion_id="AC-X-005",
                covers="R-X-005",
                kind="compiled",
                gherkin=(
                    "Given a n is 1\n"
                    "When make_widget is invoked with [n + 1, ghost.attr]\n"
                    "Then result equals nope()\n"
                ),
                file="x/AC-X-005.md",
            ),
            surface,
        ),
        # invalid: empty / garbage content
        (
            PC(
                criterion_id="AC-X-006",
                covers="R-X-006",
                kind="compiled",
                gherkin="\x00\x01 ??? {{{ \n\n",
                file="x/AC-X-006.md",
            ),
            surface,
        ),
    ]

    results = []
    for criterion, surf in cases:
        if surf is None:
            out = criterion_compiler.compile_criterion(criterion)
        else:
            out = criterion_compiler.compile_criterion(criterion, surf)
        results.append((criterion.criterion_id, out))

    assert network_sandbox == [], (
        "compile_criterion() attempted outbound network access: %r" % (network_sandbox,)
    )

    for cid, out in results:
        status = _get(out, "status")
        assert status in ("compiled", "error"), (cid, out)

    by_id = dict(results)
    assert _get(by_id["AC-X-003"], "status") == "error"
    assert _get(by_id["AC-X-004"], "status") == "error"
    assert _get(by_id["AC-X-005"], "status") == "error"


def test_cli_main_makes_no_network_calls(network_sandbox, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    valid_slug = _build_valid_component(repo_root)
    broken_slug = _build_broken_component(repo_root)

    codes = []
    for slug in (valid_slug, broken_slug):
        for cid in ("comp-" + slug, slug):
            out_dir = tmp_path / ("cli_out_" + cid)
            try:
                code = criterion_compiler.main(
                    [
                        cid,
                        "--target=pytest",
                        "--out=%s" % out_dir,
                        "--repo-root=%s" % repo_root,
                    ]
                )
            except SystemExit as exc:
                code = exc.code
            codes.append((cid, code))

    # unsupported target is a usage error, still with no network
    try:
        bad_code = criterion_compiler.main(
            [
                "comp-" + valid_slug,
                "--target=jest",
                "--repo-root=%s" % repo_root,
                "--out=%s" % (tmp_path / "cli_out_bad"),
            ]
        )
    except SystemExit as exc:
        bad_code = exc.code

    assert network_sandbox == [], (
        "compile-criteria CLI attempted outbound network access: %r" % (network_sandbox,)
    )

    for cid, code in codes:
        assert code in (0, 1, 2), (cid, code)
    assert bad_code == 2