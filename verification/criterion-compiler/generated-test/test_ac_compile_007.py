import ast
import importlib.util
import json
import sys
from pathlib import Path

import criterion_compiler


FAKE_MODULE_NAME = "fake_target_ac_compile_007"


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _string_literal_byte_spans(source: str):
    """Return (start, end) byte offsets of every string-literal node in source."""
    tree = ast.parse(source)
    lines = source.encode("utf-8").splitlines(keepends=True)
    line_starts = []
    offset = 0
    for line in lines:
        line_starts.append(offset)
        offset += len(line)
    line_starts.append(offset)

    def to_offset(lineno, col):
        return line_starts[lineno - 1] + col

    spans = []
    for node in ast.walk(tree):
        is_str_const = isinstance(node, ast.Constant) and isinstance(node.value, str)
        is_fstring = isinstance(node, ast.JoinedStr)
        if not (is_str_const or is_fstring):
            continue
        if getattr(node, "end_lineno", None) is None:
            continue
        start = to_offset(node.lineno, node.col_offset)
        end = to_offset(node.end_lineno, node.end_col_offset)
        spans.append((start, end))
    return spans


def _occurrences(haystack: bytes, needle: bytes):
    found = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return found
        found.append(idx)
        start = idx + 1


def _build_criterion(tmp_path: Path, marker: Path):
    payload = "os.system('touch " + marker.as_posix() + "')"
    payload_literal = json.dumps(payload)
    gherkin = (
        "Given a payload is " + payload_literal + "\n"
        "When target_fn is invoked with payload\n"
        'Then status equals "ok"\n'
    )
    criterion = criterion_compiler.ParsedCriterion(
        criterion_id="AC-FAKE-007",
        covers="R-FAKE-007",
        kind="compiled",
        gherkin=gherkin,
        file=str(tmp_path / "AC-FAKE-007.md"),
    )
    surface = criterion_compiler.InterfaceSurface(
        functions={"target_fn": ["text"]},
        types={},
        module_name=FAKE_MODULE_NAME,
    )
    return payload, criterion, surface


def test_ac_compile_007_payload_never_executed(tmp_path):
    marker = tmp_path / "marker"
    assert not marker.exists()

    payload, criterion, surface = _build_criterion(tmp_path, marker)

    outcome = criterion_compiler.compile_criterion(criterion, surface)

    status = _get(outcome, "status")
    assert status == "compiled", f"expected compiled, got {outcome!r}"
    assert not marker.exists(), "compiling executed the payload"

    source = _get(outcome, "source")
    assert isinstance(source, str) and source

    # Every occurrence of the payload text must lie inside a string literal.
    spans = _string_literal_byte_spans(source)
    source_bytes = source.encode("utf-8")
    occurrences = _occurrences(source_bytes, payload.encode("utf-8"))
    assert len(occurrences) >= 2, (
        "expected the payload literal in both the Given binding and the "
        f"substituted When argument; found {len(occurrences)} in:\n{source}"
    )
    needle_len = len(payload.encode("utf-8"))
    for occ in occurrences:
        occ_end = occ + needle_len
        assert any(start <= occ and occ_end <= end for start, end in spans), (
            f"payload occurrence at byte {occ} is not inside a string literal:\n{source}"
        )

    # Import the emitted file as a module, without running its test function.
    fake_dir = tmp_path / "fakemod"
    fake_dir.mkdir()
    (fake_dir / (FAKE_MODULE_NAME + ".py")).write_text(
        "class _Result:\n"
        "    status = 'ok'\n"
        "\n"
        "def target_fn(*args, **kwargs):\n"
        "    return _Result()\n",
        encoding="utf-8",
    )

    emitted_dir = tmp_path / "emitted"
    emitted_dir.mkdir()
    emitted_name = "test_ac_fake_007_emitted"
    emitted_path = emitted_dir / (emitted_name + ".py")
    emitted_path.write_text(source, encoding="utf-8")

    sys.path.insert(0, str(fake_dir))
    try:
        spec = importlib.util.spec_from_file_location(emitted_name, emitted_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[emitted_name] = module
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(emitted_name, None)
        sys.modules.pop(FAKE_MODULE_NAME, None)
        try:
            sys.path.remove(str(fake_dir))
        except ValueError:
            pass

    assert not marker.exists(), "importing the emitted module executed the payload"