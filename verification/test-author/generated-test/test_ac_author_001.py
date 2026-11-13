import json
import re
from dataclasses import dataclass, field, fields

import pytest

import test_author


CRITERION_TEXT = (
    "Given a zebra-quartz input value of 7\n"
    "When frobnicate_widget is called\n"
    "Then it returns the marker CRIT-MARKER-91f3a"
)
REQUIREMENT_TEXT = (
    "# R-WIDGET-004\n\n"
    "**R-WIDGET-004** — `frobnicate_widget(x)` MUST return the marker "
    "REQ-MARKER-7b2c4 for any zebra-quartz input."
)
INTERFACE_TEXT = (
    "# Library\n\n"
    "```\n"
    "frobnicate_widget(x: int) -> str  # IFACE-MARKER-c0d9e\n"
    "```"
)
GLOSSARY_TEXT = (
    "# Glossary\n\n"
    "- **Zebra-quartz** — a test term GLOSS-MARKER-5e8a1."
)


@dataclass(eq=False)
class FakeCriterionBundle(dict):
    """A CriterionBundle stand-in readable both as attributes and as a mapping."""

    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)
    module_names: list = field(default_factory=list)

    def __post_init__(self):
        dict.update(self, {f.name: getattr(self, f.name) for f in fields(self)})


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _norm(text):
    return " ".join(str(text).split())


def _make_backend(log_path):
    def backend(prompt, model, **params):
        record = {
            "prompt": prompt if isinstance(prompt, str) else str(prompt),
            "model": model,
            "params": {k: (v if isinstance(v, (str, int, float, bool, type(None))) else str(v))
                       for k, v in params.items()},
        }
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        prompt_str = record["prompt"]
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt_str)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", prompt_str)
        nonce = m.group(1) if m else "0" * 32

        test_code = (
            "import widget\n\n\n"
            "def test_ac_widget_004():\n"
            "    assert widget.frobnicate_widget(7) == 'CRIT-MARKER-91f3a'\n"
        )
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            f"{test_code}"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_records(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def test_ac_author_001_prompt_contains_criterion_requirement_interface_glossary(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    log_path = log_dir / "backend_calls.jsonl"

    monkeypatch.chdir(work_dir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    bundle = FakeCriterionBundle(
        component_id="comp-widget",
        criterion_id="AC-WIDGET-004",
        covers="R-WIDGET-004",
        criterion_text=CRITERION_TEXT,
        requirement_text=REQUIREMENT_TEXT,
        interface=INTERFACE_TEXT,
        glossary=GLOSSARY_TEXT,
        dependency_interfaces={},
        module_names=["widget"],
    )

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )
    assert result is not None

    records = _read_records(log_path)
    assert records, "the mock model was never called by author_test"

    recorded_input = "\n".join(
        r["prompt"] + "\n" + "\n".join(str(v) for v in r["params"].values())
        for r in records
    )
    normalized_input = _norm(recorded_input)

    assert _norm(CRITERION_TEXT) in normalized_input, "criterion text missing from model input"
    assert _norm(REQUIREMENT_TEXT) in normalized_input, "covered requirement text missing from model input"
    assert _norm(INTERFACE_TEXT) in normalized_input, "interface content missing from model input"
    assert _norm(GLOSSARY_TEXT) in normalized_input, "glossary missing from model input"

    # Distinctive markers from each section, checked raw as well.
    for marker in (
        "CRIT-MARKER-91f3a",
        "REQ-MARKER-7b2c4",
        "IFACE-MARKER-c0d9e",
        "GLOSS-MARKER-5e8a1",
    ):
        assert marker in recorded_input, f"{marker} missing from model input"

    model_call_error = _get(result, "model_call_error")
    assert model_call_error is None, f"unexpected model_call_error: {model_call_error!r}"