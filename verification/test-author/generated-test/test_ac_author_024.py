# hotdocs-criterion: sha256:f8fee4840783ef1422680b166f5ce7691994cb8772bf87918364493191377b96
import re

import test_author


FIRST_LINE = (
    "the fake's own code appends one line per call to a log file "
    "at a path the test controls"
)
SECOND_LINE = (
    "never with `str.format`, `%` or an f-string over text that holds "
    "braces or percent signs."
)

VALID_TEST = (
    "def test_placeholder():\n"
    "    assert True\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": list(self.findings),\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
        "        fh.write(" + repr("probe") + " + " + repr("\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make a widget.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_block_r_author_024(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + VALID_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1

    first_prompt = prompts[0]
    assert FIRST_LINE in first_prompt
    assert SECOND_LINE in first_prompt