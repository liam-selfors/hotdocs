import json
import textwrap
from pathlib import Path

import capability_scenario_verifier


MODEL_NAME = "fake-model"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _build_repo(root: Path) -> None:
    (root / "specs" / "product").mkdir(parents=True)
    (root / "specs" / "components" / "widget").mkdir(parents=True)
    (root / "specs" / "components" / "gadget").mkdir(parents=True)
    (root / "gen" / "widget").mkdir(parents=True)
    (root / "gen" / "gadget").mkdir(parents=True)
    (root / "gen" / "test-author").mkdir(parents=True)
    (root / "gen" / "llm-endpoint").mkdir(parents=True)

    capability_md = textwrap.dedent(
        """\
        ---
        id: P-ALPHA
        title: Alpha Capability
        status: draft
        owners: [team-alpha]
        ---

        # Alpha Capability

        ### CS-ALPHA-001

        Covers: P-ALPHA
        Kind: generated-test

        ```gherkin
        Given a widget
        When it is used
        Then it works
        ```
        """
    )
    (root / "specs" / "product" / "alpha.md").write_text(capability_md, encoding="utf-8")

    widget_component_md = textwrap.dedent(
        """\
        ---
        id: comp-widget
        title: Widget
        status: draft
        owners: [team-alpha]
        realizes: [P-ALPHA]
        sealed: false
        ---

        # Widget

        Purpose: a widget component that realizes P-ALPHA.
        """
    )
    (root / "specs" / "components" / "widget" / "component.md").write_text(
        widget_component_md, encoding="utf-8"
    )

    gadget_component_md = textwrap.dedent(
        """\
        ---
        id: comp-gadget
        title: Gadget
        status: draft
        owners: [team-alpha]
        realizes: []
        sealed: false
        ---

        # Gadget

        Purpose: a gadget component that does not realize P-ALPHA.
        """
    )
    (root / "specs" / "components" / "gadget" / "component.md").write_text(
        gadget_component_md, encoding="utf-8"
    )

    (root / "gen" / "widget" / "widget.py").write_bytes(b"def widget():\n    return 1\n")
    (root / "gen" / "gadget" / "gadget.py").write_bytes(b"def gadget():\n    return 2\n")

    fake_test_author = (
        r"""import json
from pathlib import Path


def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    log_path = Path(repo_root) / "author_calls.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"criterion_id": bundle["criterion_id"]}) + "\n")
    criterion_id = bundle["criterion_id"]
    fname = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-ALPHA/generated-test/" + fname,
            "content": "def test_x():\n    assert True\n",
        },
    }
"""
    )
    (root / "gen" / "test-author" / "test_author.py").write_text(fake_test_author, encoding="utf-8")

    fake_llm_endpoint = (
        r"""def complete(prompt, model, backend=None, **params):
    return {"text": "ok", "model_call_error": None}
"""
    )
    (root / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(
        fake_llm_endpoint, encoding="utf-8"
    )


def _run_gates(repo_root: Path, model: str = MODEL_NAME, seed: int = 0):
    return capability_scenario_verifier.run_capability_gates(
        "P-ALPHA", repo_root, model=model, seed=seed
    )


def _check(repo_root: Path):
    return capability_scenario_verifier.check_capability_provenance("P-ALPHA", repo_root)


def _read_record(repo_root: Path) -> dict:
    record_path = repo_root / "verification" / "capabilities" / "P-ALPHA" / ".provenance.json"
    return json.loads(record_path.read_text(encoding="utf-8"))


def _author_call_count(repo_root: Path) -> int:
    log_path = repo_root / "author_calls.log"
    if not log_path.exists():
        return 0
    return len(log_path.read_text(encoding="utf-8").splitlines())


def _flip_last_byte(path: Path) -> bytes:
    original = path.read_bytes()
    path.write_bytes(original[:-1] + bytes([original[-1] ^ 0xFF]))
    return original


def test_realizing_component_code_byte_change_breaks_hit(tmp_path):
    _build_repo(tmp_path)

    first = _run_gates(tmp_path)
    assert _get(first, "hit") is False

    baseline = _check(tmp_path)
    assert _get(baseline, "hit") is True
    assert _get(baseline, "capability_scenario_report") is not None

    widget_path = tmp_path / "gen" / "widget" / "widget.py"
    original = _flip_last_byte(widget_path)

    changed = _check(tmp_path)
    assert _get(changed, "hit") is False
    assert _get(changed, "capability_scenario_report") is None

    widget_path.write_bytes(original)
    restored = _check(tmp_path)
    assert _get(restored, "hit") is True


def test_capability_spec_file_change_breaks_hit(tmp_path):
    _build_repo(tmp_path)

    first = _run_gates(tmp_path)
    assert _get(first, "hit") is False

    baseline = _check(tmp_path)
    assert _get(baseline, "hit") is True

    spec_path = tmp_path / "specs" / "product" / "alpha.md"
    original = spec_path.read_bytes()
    spec_path.write_bytes(original + b"\n<!-- edited -->\n")

    changed = _check(tmp_path)
    assert _get(changed, "hit") is False
    assert _get(changed, "capability_scenario_report") is None

    spec_path.write_bytes(original)
    restored = _check(tmp_path)
    assert _get(restored, "hit") is True


def test_unrelated_component_and_pycache_changes_keep_hit(tmp_path):
    _build_repo(tmp_path)

    first = _run_gates(tmp_path)
    assert _get(first, "hit") is False

    baseline = _check(tmp_path)
    assert _get(baseline, "hit") is True

    gadget_path = tmp_path / "gen" / "gadget" / "gadget.py"
    _flip_last_byte(gadget_path)

    after_unrelated = _check(tmp_path)
    assert _get(after_unrelated, "hit") is True
    assert _get(after_unrelated, "capability_scenario_report") is not None

    pycache_dir = tmp_path / "gen" / "widget" / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "widget.cpython-311.pyc").write_bytes(b"\x00\x01\x02binary-garbage")

    after_pycache = _check(tmp_path)
    assert _get(after_pycache, "hit") is True
    assert _get(after_pycache, "capability_scenario_report") is not None


def test_run_capability_gates_rehashes_after_code_change(tmp_path):
    _build_repo(tmp_path)

    first = _run_gates(tmp_path)
    assert _get(first, "hit") is False
    calls_after_first = _author_call_count(tmp_path)
    assert calls_after_first >= 1

    record_before = _read_record(tmp_path)
    content_hash_before = record_before["content_hash"]

    widget_path = tmp_path / "gen" / "widget" / "widget.py"
    _flip_last_byte(widget_path)

    second = _run_gates(tmp_path)
    assert _get(second, "hit") is False

    calls_after_second = _author_call_count(tmp_path)
    assert calls_after_second > calls_after_first

    record_after = _read_record(tmp_path)
    content_hash_after = record_after["content_hash"]
    assert content_hash_after != content_hash_before