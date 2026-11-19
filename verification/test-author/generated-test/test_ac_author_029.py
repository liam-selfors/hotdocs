# hotdocs-criterion: sha256:cc17af5dc84a304a910327bcc8f1b450471c368042d4f67b05ee38785ca5777e
import dataclasses
import json
from pathlib import Path

import pytest

import test_author


@dataclasses.dataclass
class FakeResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: object
    model_call_error: object
    repair_attempts: int
    probe_findings: list


FIXED_BUNDLE = {
    "component_id": "comp-foo",
    "criterion_id": "AC-FOO-001",
    "covers": "R-FOO-001",
    "criterion_text": "Given x When y Then z",
    "requirement_text": "R-FOO-001 text",
    "interface": "",
    "glossary": "",
    "dependency_interfaces": {},
    "testing": "",
}


def plant_assembler(root):
    base = Path(root) / "gen" / "spec-bundle-assembler"
    base.mkdir(parents=True, exist_ok=True)
    source = (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('not used')\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(FIXED_BUNDLE) + ")\n"
    )
    (base / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")


def make_stub(seeds, model_call_error):
    def stub(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
        seeds.append(seed)
        if model_call_error is None:
            file = {"path": "p.py", "content": "x"}
        else:
            file = None
        return FakeResult(
            component_id="comp-foo",
            criterion_id="AC-FOO-001",
            model=model,
            seed=seed,
            prompt_version="v1",
            cache_hit=False,
            file=file,
            model_call_error=model_call_error,
            repair_attempts=0,
            probe_findings=[],
        )

    return stub


@pytest.fixture
def cli_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    plant_assembler(root)
    return root


def valid_argv(root):
    return ["comp-foo", "AC-FOO-001", "--model", "m", "--repo-root", str(root)]


def test_success_text_and_json(cli_root, monkeypatch, capsys):
    seeds = []
    monkeypatch.setattr(test_author, "author_test", make_stub(seeds, None))

    code = test_author.main(valid_argv(cli_root))
    out, err = capsys.readouterr()
    assert code == 0
    assert out == "AC-FOO-001: wrote p.py\n"
    assert seeds == [0]

    code = test_author.main(valid_argv(cli_root) + ["--format=json"])
    out, err = capsys.readouterr()
    assert code == 0
    doc = json.loads(out)
    assert doc["criterion_id"] == "AC-FOO-001"


def test_model_call_error(cli_root, monkeypatch, capsys):
    seeds = []
    monkeypatch.setattr(
        test_author,
        "author_test",
        make_stub(seeds, {"category": "network", "message": "down"}),
    )
    code = test_author.main(valid_argv(cli_root))
    out, err = capsys.readouterr()
    assert code == 1
    assert out == "AC-FOO-001: model_call_error network: down\n"


@pytest.mark.parametrize(
    "extra, cause",
    [
        (None, "expected <component-id> and <criterion-id>"),
        (["--format=xml"], "--format must be json or text"),
        (["--seed=x"], "--seed must be an integer"),
        (["--bogus"], "unknown argument --bogus"),
        (["--model"], "--model requires a value"),
    ],
)
def test_usage_errors(cli_root, monkeypatch, capsys, extra, cause):
    seeds = []
    monkeypatch.setattr(test_author, "author_test", make_stub(seeds, None))
    if extra is None:
        argv = ["comp-foo"]
    else:
        argv = valid_argv(cli_root) + extra
    code = test_author.main(argv)
    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert err.startswith("usage error: " + cause)