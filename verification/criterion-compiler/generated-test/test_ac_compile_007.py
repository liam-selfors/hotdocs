# hotdocs-criterion: sha256:083a9dc8ce2d4a09de0a8dddd3886b4ee949d852cb8c0faa99ae040d7115b3be
import importlib.util
import io
import json
import sys
import tokenize
import uuid

import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _string_literal_spans(source):
    lines = source.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def offset(row, col):
        return starts[row - 1] + col

    spans = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.STRING:
            spans.append((offset(*tok.start), offset(*tok.end)))
    return spans


def _occurrences(text, needle):
    result = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            return result
        result.append(idx)
        start = idx + 1


def test_payload_is_never_evaluated(tmp_path):
    marker = tmp_path / "pwned_marker"
    payload = "os.system('touch " + str(marker) + "')"
    payload_literal = json.dumps(payload)

    suffix = uuid.uuid4().hex[:10]
    target_module_name = "fake_target_" + suffix

    gherkin = (
        "Given a payload is " + payload_literal + "\n"
        "When run_it is invoked with payload\n"
        'Then status equals "ok"\n'
    )
    criterion = criterion_compiler.ParsedCriterion(
        criterion_id="AC-FAKE-001",
        covers="R-FAKE-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/fake/acceptance/AC-FAKE-001.md",
    )
    surface = criterion_compiler.InterfaceSurface(
        functions={"run_it": ["text"]},
        types={},
        module_name=target_module_name,
    )

    out = criterion_compiler.compile_criterion(criterion, surface)

    assert field(out, "status") == "compiled", out
    assert not marker.exists()

    source = field(out, "source")
    assert isinstance(source, str)

    occurrences = _occurrences(source, payload)
    assert len(occurrences) >= 1, source
    spans = _string_literal_spans(source)
    for occ in occurrences:
        end = occ + len(payload)
        assert any(s <= occ and end <= e for s, e in spans), (
            "payload text at offset " + repr(occ) + " is not inside a string literal:\n" + source
        )

    # Import the emitted file as a module, without running its test function.
    fake_dir = tmp_path / "fake_target"
    fake_dir.mkdir()
    (fake_dir / (target_module_name + ".py")).write_text(
        "def run_it(*args, **kwargs):\n"
        "    class _R:\n"
        "        status = 'ok'\n"
        "    return _R()\n"
    )
    emitted_dir = tmp_path / "emitted"
    emitted_dir.mkdir()
    emitted_name = "test_emitted_" + suffix
    emitted_path = emitted_dir / (emitted_name + ".py")
    emitted_path.write_text(source)

    sys.path.insert(0, str(fake_dir))
    try:
        load_module(str(emitted_path), emitted_name)
    finally:
        try:
            sys.path.remove(str(fake_dir))
        except ValueError:
            pass
        sys.modules.pop(emitted_name, None)
        sys.modules.pop(target_module_name, None)

    assert not marker.exists()